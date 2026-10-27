"""Remaster names of the images of the original scenarios.

Other images: the most voted name. Characters (有珠制服01a(近)|d -> ari_n_12_02_03): character,
size, outfit and pose numbers as voted; the expression number, when never seen, is found between
the nearest known expressions of the same pose and size, when exactly as many letters are used
between them as numbers are free."""
import collections
import re

NAME = re.compile(r'^(有珠|草十郎|青子)(制服(?:ケープ無帽|ケープ|コート|マフラー)?|私服)(\d\d[a-z]?)\((近|大|中|遠|全)\)(?:\|(\w+))?$')
SIZES = {'近': 'n', '大': 'l', '中': 'm', '遠': 's', '全': 'a'}
CHARACTERS = {'有珠': 'ari', '草十郎': 'sou', '青子': 'aok'}
REMASTER = re.compile(r'^(\w+)_([a-z])_(\d\d)_(\d\d)_(\d\d)$')
# Images of 7-1b found in the remaster by hand
FOUND = {
	'ev0801(有珠単)': 'img0705', 'im11コマドリ降着01b': 'img1866',
	'im16l双子ブタ(影)_オブジェ(豚01ワニ付上)': 'img2020', 'im16l双子ブタ(影)_オブジェ(豚01ワニ付下)': 'img2019',
	'有珠私服04a(近)': 'ari_n_01_19_00', '青子制服マフラー02c(遠)': 'aok_s_16_10_00',
	'青子制服マフラー02c(遠)|m': 'aok_s_16_10_01',
	# the whole image (the most voted is a close-up the remaster made for zoomed shots)
	'bg01l久遠寺邸03居間(ソファ無し)-(昼)': 'img0045',
	# img3491, missing from the image table of the engine: shown as img1140 (utils/steam/hidden_scene.py)
	'im03l裏庭のポンプ': 'img1140',
	# eyes closed, cut out on one eye (wink); unknown expression otherwise replaced by open eyes
	'有珠制服02c(近)|k2': 'ari_n_12_10_08',
}


class Names:
	def __init__(self, learned):
		self.votes = learned.votes
		self.resources = {name.lower() for name in learned.resources}
		self.letters = collections.defaultdict(set)  # expressions used for each pose and size
		for storage in learned.storages:
			m = NAME.match(storage)
			if m:
				self.letters[m.groups()[:4]].add(m[5] or '')
		codes = {}
		for storage, counter in self.votes.items():
			m, r = NAME.match(storage), REMASTER.match(counter.most_common(1)[0][0])
			if m and r:
				codes.setdefault((m[1], m[2], m[3]), collections.Counter())[(r[3], r[4])] += 1
		self.codes = {key: counter.most_common(1)[0][0] for key, counter in codes.items()}

	def exists(self, name: str) -> bool:
		return name.lower() + '.mzp' in self.resources

	def _voted(self, storage: str, m) -> str | None:
		"""Most voted name; for a character, of its usual outfit and pose (pages that do not match
		between the releases vote for the images of another outfit)."""
		prefix = f'{CHARACTERS[m[1]]}_{SIZES[m[4]]}_' if m else ''
		if m and (m[1], m[2], m[3]) in self.codes:
			prefix += '_'.join(self.codes[(m[1], m[2], m[3])]) + '_'
		for name, _ in self.votes.get(storage, collections.Counter()).most_common():
			if name.startswith(prefix):
				return name
		return None

	def _expression(self, m) -> str | None:
		if (m[1], m[2], m[3]) not in self.codes:
			return None
		outfit, pose = self.codes[(m[1], m[2], m[3])]
		prefix = f'{CHARACTERS[m[1]]}_{SIZES[m[4]]}_{outfit}_{pose}_'
		letter = m[5] or ''
		if not letter:
			return prefix + '00'
		order = sorted(self.letters[m.groups()[:4]], key=lambda x: (x != '', x))
		known = {}
		for other in order:
			name = self._voted(f'{m[1]}{m[2]}{m[3]}({m[4]})' + (f'|{other}' if other else ''), m)
			if name and name.startswith(prefix):
				known[other] = int(name[-2:])
			elif other == '':
				known[''] = 0
		position = order.index(letter)
		before = [x for x in order[:position] if x in known]
		after = [x for x in order[position + 1:] if x in known]
		numbers = sorted(int(n[len(prefix):len(prefix) + 2]) for n in self.resources
		                 if n.startswith(prefix) and re.fullmatch(r'\d\d\.mzp', n[len(prefix):]))
		low = known[before[-1]] if before else -1
		high = known[after[0]] if after else (numbers[-1] + 1 if numbers else None)
		if high is None:
			return None
		between = order[(order.index(before[-1]) + 1 if before else 0):(order.index(after[0]) if after else len(order))]
		if len(between) != high - low - 1:
			return None
		return prefix + f'{low + 1 + between.index(letter):02d}'

	def remaster(self, storage: str) -> str | None:
		"""Existing remaster image of a storage; an unknown expression gives the pose without it."""
		for candidate in (storage, storage.split('|')[0]):
			m = NAME.match(candidate)
			name = FOUND.get(candidate) or self._voted(candidate, m) or (self._expression(m) if m else None)
			if name and self.exists(name):
				return name
		return None

	def blur(self, name: str, y: int, x: int) -> tuple[int, int]:
		"""Blur of an image among its pre-blurred variants (name_YY_XX.mzp), the nearest one."""
		if not y and not x:
			return 0, 0
		variants = [(0, 0)]
		pattern = re.compile(re.escape(name.lower()) + r'_(\d\d)_(\d\d)\.mzp')
		for resource in self.resources:
			m = pattern.fullmatch(resource)
			if m:
				variants.append((int(m[1]), int(m[2])))
		return min(variants, key=lambda v: ((v[0] - y) ** 2 + (v[1] - x) ** 2, v))  # the least blurred on a tie

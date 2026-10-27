"""What the conversion learns from the scenes that exist in both releases, page by page (the page
N of an original scenario is the page N + 2 of its remaster script, after its preamble):
- the remaster name of each original image, voted over the pages showing as many images in both;
- the priority of each fg index, the effect and blend arguments, the half sizes of the large
  backgrounds (left operands of their position expressions)."""
import collections
import os
import re
from dataclasses import dataclass, field

from tools.scene_conversion import original, remaster
from utils.steam import lenzu
from utils.steam.hfa import archive_names, find_in_archives

IMAGE_COMMANDS = ('bg', 'fg', 'chgfg', 'partbg')
EXCLUDE = 'data00999.hfa'


@dataclass
class Learned:
	votes: dict = field(default_factory=lambda: collections.defaultdict(collections.Counter))
	storages: set = field(default_factory=set)  # every storage of the original scenarios
	resources: set = field(default_factory=set)  # every resource name of the remaster
	priority: dict = field(default_factory=dict)
	effect: dict = field(default_factory=dict)
	blend: dict = field(default_factory=dict)
	halves: dict = field(default_factory=dict)


def script_name(scene: str) -> str:
	"""Remaster script of an original scenario: 1.5-3 -> 1dot5_3.chs."""
	return scene.replace('-', '_').replace('.', 'dot') + '.chs'


def _best(counters: dict) -> dict:
	return {key: counter.most_common(1)[0][0] for key, counter in counters.items()}


def learn(scenario_dir: str, game_dir: str) -> Learned:
	learned = Learned(resources=archive_names(game_dir, exclude=EXCLUDE))
	priority, effect, blend, halves = (collections.defaultdict(collections.Counter) for _ in range(4))
	for name in sorted(os.listdir(scenario_dir)):
		if not name.endswith('.ks'):
			continue
		text = original.read(os.path.join(scenario_dir, name))
		learned.storages |= set(re.findall(r'storage=([^\s\]]+)', text))
		data = find_in_archives(game_dir, script_name(name[:-3]), exclude=EXCLUDE)
		if data is None:
			continue
		remaster_pages = remaster.pages(lenzu.decompress(data))
		for k, page in enumerate(original.pages(text)):
			if k + 2 >= len(remaster_pages):
				break
			commands = [(cmd, a) for cmd, a in page if cmd in IMAGE_COMMANDS and 'storage' in a]
			ops = remaster_pages[k + 2]
			images = [i for i, (op, args, _) in enumerate(ops) if op in (576, 578) and len(args) > 1 and isinstance(args[-2], str)]
			if len(commands) != len(images):
				continue
			for (cmd, a), i in zip(commands, images):
				op, args, bases = ops[i]
				learned.votes[a['storage']][args[-2]] += 1
				if op != 576 or cmd not in ('bg', 'fg'):
					continue
				layer = args[-1]
				following = {}
				for op2, args2, _ in ops[i + 1:]:
					if op2 in (576, 578, 512, 'text'):
						break
					if args2 and args2[-1] == layer:
						following.setdefault(op2, args2)
				if cmd == 'fg' and len(args) >= 18:
					priority[a.get('index', '')][args[-7]] += 1
				effect[a.get('effect', '')][tuple(following.get(595, [None, None])[:2])] += 1
				blend[a.get('type', '')][tuple(following.get(594, [None, None, None])[:3])] += 1
				if cmd == 'bg' and 'left' in a and 'top' in a and len(bases) >= 2:
					halves[args[-2]][tuple(bases[-2:])] += 1
	learned.priority = {int(k): v for k, v in _best(priority).items() if k.lstrip('-').isdigit()}
	learned.effect = {k: v for k, v in _best(effect).items() if v[1] is not None}
	learned.blend = {k: v for k, v in _best(blend).items() if v[0] is not None}
	learned.halves = _best(halves)
	return learned

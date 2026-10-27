"""Translation of the commands of an original scenario into remaster instructions (opcode, args).

Positions are in units of 1/4 pixel at 1080p: original pixels × 15/32. A background alternates
between layers 0 and 1, each image gets a free layer; a transition marks the layers that go away
(593), crossfades (512), then removes them (577). A background that clears the images fades in
from black instead. Effects, zoom, rotation, brightness, contrast and blur are instructions
following the image (595, 582, 583, 597, 596, 598); the remaster has no zoom or rotation
animation of its own, so the keyframe animations only move the images and change their opacity
(579, 581)."""
import re

NEG = -2147483648  # "unchanged"
UNIT = 15 / 32
LARGE_HALVES = (247, 410)  # half sizes, in units, of most large backgrounds
SCREEN_HALVES = (135, 240)
LAST_LAYER = 39  # the engine has the layers 2 to 39 for the images
BORDER_COLORS = {'none': 0, None: 1, '0x000000': 1, '0xFFFFFF': 2, '0xffffff': 2}
COMMANDS = ('fg', 'bg', 'partbg', 'trans', 'clall', 'chgfg', 'clfg', 'movefg', 'movepartbg', 'fgact', 'bgact',
            'se', 'seact', 'sestop', 'fadese', 'play', 'playstop', 'wait')


def number(value, default=0.0) -> float:
	try:
		return float(value)
	except (TypeError, ValueError):
		return default


def unit(value) -> int:
	return int(number(value) * UNIT)


def unit_y(value) -> int:
	"""Vertical position: the remaster places the images slightly lower than × 15/32."""
	return int(number(value) * 0.4716 + 0.3)


def groups(text: str) -> list[str]:
	"""Top-level groups of keys=(...)(...); the names may contain parentheses."""
	result, depth, start = [], 0, 0
	for i, c in enumerate(text):
		if c == '(':
			start = i + 1 if depth == 0 else start
			depth += 1
		elif c == ')':
			depth -= 1
			if depth == 0:
				result.append(text[start:i])
	return result


def keyframes(a: dict) -> list[dict]:
	"""Frames of an animation: keys=(time, accel, interpolation l/n, values of the props)."""
	props = [p.lstrip('-') for p in a.get('props', '').split(',')]
	frames, current = [], {}
	for key in groups(a.get('keys', '')):
		values = re.split(r',(?![^(]*\))', key)
		mode = values[2] if len(values) > 2 and values[2] else (frames[-1]['mode'] if frames else 'l')
		current.update({p: v for p, v in zip(props, values[3:]) if v not in ('', '~')})
		frames.append({'time': number(values[0]), 'mode': mode, **current})
	return frames


class Translator:
	def __init__(self, learned, names, bg_layer=1, scales=None):
		self.learned, self.names = learned, names
		self.bg_layer = bg_layer
		self.scales = scales or {}  # image -> zoom factor (remaster image smaller than the original)
		self.out = []
		self.next_layer = 2
		self.fore = {}        # layer -> storage, shown
		self.back = {}        # layer -> storage, created since the last transition
		self.cleared = set()  # shown layers removed at the next transition
		self.pending_bg = None  # previous background layer, until the transition
		self.ids = {}         # id attribute -> layer
		self.positions = {}   # layer -> (y, x)
		self.buffers = {}     # sound -> buffer
		self.next_buffer = 3
		self.last_buffer = None

	def command(self, name: str, a: dict) -> bool:
		if name not in COMMANDS:
			return False
		getattr(self, name)(a)
		return True

	def emit(self, opcode, *args):
		self.out.append((opcode, list(args)))

	def layer(self) -> int:
		used = set(self.fore) | set(self.back) | self.cleared
		for _ in range(LAST_LAYER):
			if self.next_layer > LAST_LAYER:
				self.next_layer = 2
			layer = self.next_layer
			self.next_layer += 1
			if layer not in used:
				return layer
		raise ValueError('no free layer')

	def priority(self, index) -> int:
		table = self.learned.priority
		index = int(number(index, 1000))
		if index in table:
			return table[index]
		below = max((k for k in table if k <= index), default=min(table))
		above = min((k for k in table if k >= index), default=max(table))
		if above == below:
			return table[below]
		return int(table[below] + (table[above] - table[below]) * (index - below) / (above - below))

	def zoom(self, layer, a, default):
		if 'zoom' in a:
			z = int(round(number(a['zoom']) * 10))
			self.emit(582, 0, 0, 0, z, z, z, z, layer)
		elif 'zoomx' in a or 'zoomy' in a:
			zx = int(round(number(a['zoomx']) * 10)) if 'zoomx' in a else default
			zy = int(round(number(a['zoomy']) * 10)) if 'zoomy' in a else default
			self.emit(582, 0, 0, 0, zy, zx, zy, zx, layer)

	def image(self, layer, a, name, y, x, bg=False, clip=(0, 0, 0, 0, 0, 0)):
		"""An image and its attributes, in the order of the remaster."""
		if name in self.scales:
			zooms = {k: number(a[k]) for k in ('zoomx', 'zoomy') if k in a} or {'zoom': number(a.get('zoom'), 100)}
			a = {k: v for k, v in a.items() if k not in ('zoom', 'zoomx', 'zoomy')}
			a.update({k: str(v * self.scales[name]) for k, v in zooms.items()})
		blur = self.names.blur(name, int(number(a.get('yblur', a.get('blur')))), int(number(a.get('xblur', a.get('blur')))))
		priority = 2 if bg else self.priority(a.get('index'))
		self.emit(576, *clip, -1, *blur, 'CC', 0, priority, int(number(a.get('opacity'), 255)), 1000, y, x, name, layer)
		self.positions[layer] = (y, x)
		rotation = -int(round(number(a.get('rotate')) * 100))
		if bg:
			self.emit(583, 0, 0, 0, 0, rotation, rotation, layer)
			self.zoom(layer, a, 1000)
		effect = a.get('effect')
		if m := re.fullmatch(r'mono([0-9a-fA-F]{6})', effect or ''):
			self.emit(595, int(m[1], 16), 1, layer)
		elif effect in self.learned.effect:
			self.emit(595, *self.learned.effect[effect], layer)
		if a.get('type') in self.learned.blend:
			self.emit(594, *self.learned.blend[a['type']], layer)
		if not bg:
			self.zoom(layer, a, NEG)
			if 'rotate' in a:
				self.emit(583, 0, 0, 0, 0, rotation, rotation, layer)
		if 'brightness' in a:
			self.emit(597, int(number(a['brightness'])), layer)
		if 'contrast' in a:
			self.emit(596, int(number(a['contrast'])), layer)
		if blur != (0, 0):
			self.emit(598, *blur, layer)

	def transition(self, time, noback):
		removed = sorted(self.cleared)
		for layer in removed:
			self.emit(593, 0, layer)
		self.emit(512, 0, 256, -1 if noback else 0, 0, time, 0)
		for layer in removed:
			self.emit(577, layer)
			self.fore.pop(layer, None)
		if self.pending_bg is not None:
			self.emit(577, self.pending_bg)
		self.emit(512, 0, 256, 0, 0, 0, 1)
		self.fore.update(self.back)
		self.back, self.cleared, self.pending_bg = {}, set(), None

	def fade_out(self, layer, time):
		self.emit(593, 0, layer)
		self.emit(512, 0, 256, 0, 0, time, 0)
		self.emit(577, layer)
		self.emit(512, 0, 256, 0, 0, 0, 1)

	def find(self, storage):
		"""Layer (and its dict) showing the same image as storage, whatever its expression."""
		base = storage.split('|')[0]
		for layers in (self.back, self.fore):
			for layer, shown in reversed(list(layers.items())):
				if shown.split('|')[0] == base:
					return layer, layers
		return None, None

	# ---- images
	def fg(self, a):
		name = self.names.remaster(a.get('storage', ''))
		if name:
			layer = self.layer()
			self.image(layer, a, name, unit_y(a.get('vcenter', 288)), unit(a.get('center', 512)))
			self.back[layer] = a['storage']
			if 'id' in a:
				self.ids[a['id']] = layer

	def bg(self, a):
		storage = a.get('storage', '')
		name = self.names.remaster(storage)
		if not name:
			return
		old, new = self.bg_layer, 1 - self.bg_layer
		if a.get('noclear') != '1':
			self.cleared |= set(self.fore)
		if 'left' in a or 'top' in a:
			hy, hx = self.learned.halves.get(name, LARGE_HALVES)
			y, x = hy + unit(a.get('top', 0)), hx + unit(a.get('left', 0))
		else:
			y, x = 136, 240
		self.emit(593, 1, old)
		self.image(new, a, name, y, x, bg=True)
		self.bg_layer = new
		timed = 'time' in a or 'rule' in a
		if timed and a.get('noclear') != '1':
			# faded in from black, the images removed
			self.emit(581, 0, 0, 0, 0, new)
			self.emit(593, 20040, new)
			self.emit(512, 0, 256, 0, 0, 0, 1)
			self.emit(338, -1)
			self.emit(581, 0, int(number(a.get('time'))), 255, NEG, new)
			self.emit(639, 1, 8, new)
			for layer in sorted(self.cleared | set(self.fore) | set(self.back)):
				self.emit(577, layer)
			self.emit(577, old)
			self.emit(593, 2, new)
			self.emit(512, 0, 256, 0, 0, 0, 1)
			self.fore, self.back, self.cleared = {}, {}, set()
			return
		self.pending_bg = old
		if timed:
			self.transition(int(number(a.get('time'))), a.get('noback') == '1')

	def partbg(self, a):
		"""Part of an image (from srcleft, srctop) shown in a rectangle of the screen."""
		storage = a.get('storage', '')
		name = self.names.remaster(storage)
		if not name:
			return
		width, height = number(a.get('width'), 1024), number(a.get('height'), 576)
		left = number(a.get('center'), 512) - width / 2
		top = number(a.get('vcenter'), 288) - height / 2
		clip = (BORDER_COLORS.get(a.get('bordercolor'), 4), int(round(number(a.get('bordersize'), 40) * 1.875)),
		        *(int(round(v * 1.875)) for v in (height, width, top, left)))
		shown, _ = self.find(storage)
		if shown is not None and re.match(r'(有珠|草十郎|青子)', storage):
			# part of another expression of a character shown (eyes, mouth): same canvas, same place
			y, x = self.positions[shown]
		else:
			large = re.match(r'(bg|im|ev)\d*l', storage)
			hy, hx = self.learned.halves.get(name, LARGE_HALVES if large else SCREEN_HALVES)
			y, x = unit(top - number(a.get('srctop'))) + hy, unit(left - number(a.get('srcleft'))) + hx
		# the zoom and rotation of a part are those of its source
		transform = ('zoom', 'zoomx', 'zoomy', 'rotate')
		attributes = {k: v for k, v in a.items() if k not in transform}
		attributes.update({k: a['src' + k] for k in transform if 'src' + k in a})
		layer = self.layer()
		self.image(layer, attributes, name, y, x, clip=clip)
		self.back[layer] = storage
		if 'id' in a:
			self.ids[a['id']] = layer
		if 'rule' in a or 'time' in a:
			self.transition(int(number(a.get('time'))), True)

	def trans(self, a):
		self.transition(int(number(a.get('time'))), a.get('noback') == '1')

	def clall(self, a):
		self.cleared |= set(self.fore)

	def chgfg(self, a):
		storage = a.get('storage', '')
		old, layers = self.find(storage)
		name = self.names.remaster(storage)
		if old is None or not name:
			return
		new = self.layer()
		self.emit(578, old, *[NEG] * 9, 'CC', *[NEG] * 6, name, new)
		self.fade_out(old, int(number(a.get('time'))))
		del layers[old]
		layers[new] = storage

	def clfg(self, a):
		old, layers = self.find(a.get('storage', ''))
		if old is not None:
			self.fade_out(old, int(number(a.get('time'))))
			del layers[old]

	def movefg(self, a):
		layer, _ = self.find(a.get('storage', ''))
		if layer is None:
			return
		time = int(number(a.get('time')))
		if 'opacity' in a:
			self.emit(581, 0, time, int(number(a['opacity'])), NEG, layer)
		if 'center' in a or 'vcenter' in a:
			self.emit(579, 'CC', 0, time, unit_y(a.get('vcenter')), unit(a.get('center')), NEG, NEG, layer, 0)

	def movepartbg(self, a):
		layer = self.ids.get(a.get('id'))
		if layer is not None and 'opacity' in a:
			self.emit(581, 0, int(number(a.get('time'))), int(number(a['opacity'])), NEG, layer)

	# ---- keyframe animations
	def animate(self, layer, frames, position):
		"""Moves (position(frame): center in units) and opacity changes between the frames."""
		for start, end in zip(frames, frames[1:]):
			delay, time = int(start['time']), int(end['time'] - start['time'])
			if start['mode'] == 'n':  # no interpolation: the values of the next frame at its time
				delay, time = int(end['time']), 0
			if position(end) != position(start):
				self.emit(579, 'CC', delay, time, *position(end), NEG, NEG, layer, 0)
			if 'opacity' in end and end.get('opacity') != start.get('opacity'):
				self.emit(581, delay, time, int(number(end['opacity'])), NEG, layer)

	def fgact(self, a):
		frames = keyframes(a)
		if not frames:
			return
		layer = self.ids.get(a.get('id'))
		if layer is None:
			layer, _ = self.find(frames[0].get('storage', a.get('storage', '')))
		if layer is not None:
			self.animate(layer, frames, lambda f: (unit_y(f.get('vcenter', 288)), unit(f.get('center', 512))))

	def bgact(self, a):
		frames = keyframes(a)
		name = self.names.remaster(frames[0].get('storage', a.get('storage', ''))) if frames else None
		if name:
			hy, hx = self.learned.halves.get(name, LARGE_HALVES)
			self.animate(self.bg_layer, frames, lambda f: (hy + unit(f.get('top', 0)), hx + unit(f.get('left', 0))))

	# ---- sounds and waits
	def buffer(self, sound: str) -> int:
		self.buffers[sound] = self.last_buffer = self.next_buffer
		self.next_buffer += 1
		return self.last_buffer

	def se(self, a):
		sound = a.get('storage', '').upper()
		self.emit(400, int(number(a.get('delay'))), int(number(a.get('time'))), 64 + int(number(a.get('pan')) * 64 / 100),
		          int(number(a.get('volume'), 100)), sound, int(number(a.get('loop'))), self.buffer(sound))

	def seact(self, a):
		for key in groups(a.get('keys', '')):
			values = key.split(',')
			if len(values) > 4 and values[1] == 'play':
				sound = values[2].upper()
				self.emit(400, int(number(values[0])), int(number(values[3])), 64, int(number(values[4], 100)),
				          sound, 0, self.buffer(sound))

	def sestop(self, a):
		buffer = self.buffers.get(a.get('storage', '').upper(), self.last_buffer)
		if buffer is not None:
			self.emit(405, 0, int(number(a.get('time'))), 0, buffer)

	def fadese(self, a):
		buffer = self.buffers.get(a.get('storage', '').upper(), self.last_buffer)
		if buffer is not None:
			self.emit(406, 0, int(number(a.get('time'))), int(number(a.get('volume'))), 0, 0, buffer)

	def play(self, a):
		if m := re.fullmatch(r'm(\d+)', a.get('storage', '')):
			self.emit(384, 0, int(number(a.get('time'))), 1, int(number(a.get('volume'), 100)), int(m[1]))

	def playstop(self, a):
		self.emit(389, 0, int(number(a.get('time'))))

	def wait(self, a):
		self.emit(272, 0, 1, int(number(a.get('time'))))

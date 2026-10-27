"""Converts the staging of the original 2012 scene 7-1b into remaster instructions
(sources/scene-7-1b.jsonl, assembled by utils/steam/hidden_scene.py at the build).

Usage, from the project folder:
    python -m tools.scene_conversion.convert <scenario folder> [--check]
The scenario folder holds the .ks files of data.xp3 of the 2012 release (extracted with
extend-area/extract-xp3). --check also translates the scenes of chapter 7 that exist in both
releases and prints how much of the remaster instructions it finds again."""
import difflib
import json
import os
import re
import sys

import utils.config_importer as conf
from tools.scene_conversion import original, remaster
from tools.scene_conversion.learn import EXCLUDE, learn, script_name
from tools.scene_conversion.names import Names
from tools.scene_conversion.translator import Translator
from utils.steam import lenzu
from utils.steam.hfa import find_in_archives
from utils.steam.hidden_scene import INSTRUCTIONS
from utils.utils import get_file_lines

SCENE = '7-1b'
FIRST_LINE, LAST_LINE = 8962, 9171  # of the scene in script_text (from 1)
# Voices of the scene, in order: Sōjūrō (A30), Aoko (A10), and the robin (BA0, played on narration)
SOJURO_LINES = [9020, 9028, 9033, 9034, 9036, 9041, 9044, 9045, 9048, 9049, 9057, 9059, 9061, 9066, 9069,
                9076, 9090, 9093, 9094, 9095, 9096, 9097, 9098, 9099, 9109, 9119, 9120, 9123, 9128, 9129,
                9130, 9131, 9137, 9138, 9143, 9157, 9160, 9164, 9165]
VOICES = {line: (416, f'A30_7_1B_{i:04d}') for i, line in enumerate(SOJURO_LINES)}
VOICES.update({9161: (416, 'A30_7_1B_9000'), 9038: (416, 'A10_7_1B_0000'),
               9006: (424, 'BA0_7_1B_0000'), 9012: (424, 'BA0_7_1B_0001')})
# The pump, shown as img1140 (see utils/steam/hidden_scene.py): half size of the original image
# (775x1050) in units, and zoom of the smaller remaster image (930 pixels wide instead of 1453),
# corrected by 1.22 as measured against the original in game
PUMP, PUMP_HALVES, PUMP_SCALE = 'img1140', (246, 182), 1453 / 930 * 1.22
IGNORED = {'call', 'return', 'eval', 'stopaction', 'invisibleframe', 'visibleframe', 'textoff', 'texton',
           'position', 'wt', 'wm'}
CHECKED = ['7-1', '7-2', '7-3', '7-5', '7-6', '7-7', '7-8']
NOT_COMPARED = {'text', 416, 424, 321, 322, 298, 233, 632}


def normalize(text: str) -> str:
	"""Text without rubies, tags nor spaces, to find the script lines in the scenario."""
	text = re.sub(r'\[[^\]]*\]', '', re.sub(r'<([^|>]*)\|[^>]*>', r'\1', text))
	return text.replace('　', '').replace(' ', '').strip()


def translate(text: str, translator: Translator, script_lines: list[str]) -> list:
	"""Instructions of the scene, with its text lines ('text', line, page end) and voices."""
	out, n, rest, in_script = [], FIRST_LINE, normalize(script_lines[FIRST_LINE - 1]), False
	for line in text.splitlines():
		line = line.strip()
		if in_script:
			in_script = not line.startswith('@endscript')
		elif not line or line.startswith((';', '*')):
			continue
		elif command := original.command(line):
			name, attributes = command
			if name == 'iscript':
				in_script = True
			elif name == 'r':
				out.append((322, []))
			elif name == 'pg':
				last = max(i for i, item in enumerate(out) if item[0] == 'text')
				out[last] = ('text', out[last][1], True)
				out.append(('page', []))
			elif name not in IGNORED:
				translator.out = []
				if not translator.command(name, attributes):
					print(f'ignored command: @{name}')
				out += translator.out
		else:
			part = normalize(line)
			while part:
				if rest.startswith(part):
					rest, part = rest[len(part):], ''
				elif part.startswith(rest):
					part, rest = part[len(rest):], ''
				else:
					raise ValueError(f'script line {n} not found in the scenario: {rest!r} / {part!r}')
				if not rest:
					if n in VOICES:
						out.append((VOICES[n][0], [0, VOICES[n][1]]))
					out.append(('text', n, False))
					n += 1
					rest = normalize(script_lines[n - 1]) if n <= LAST_LINE else ''
	if n != LAST_LINE + 1:
		raise ValueError(f'the scenario ends at script line {n}')
	return out


def check(scenario_dir: str, learned, names):
	same = total = 0
	for scene in CHECKED:
		pages = remaster.pages(lenzu.decompress(find_in_archives(conf.game_folder, script_name(scene), exclude=EXCLUDE)))
		translator = Translator(learned, names)
		for k, page in enumerate(original.pages(original.read(os.path.join(scenario_dir, scene + '.ks')))):
			if k + 2 >= len(pages):
				break
			translator.out = []
			for name, attributes in page:
				translator.command(name, attributes)
			mine = [str(op) for op, _ in translator.out]
			theirs = [str(op) for op, _, _ in pages[k + 2] if op not in NOT_COMPARED]
			matcher = difflib.SequenceMatcher(None, mine, theirs, autojunk=False)
			same += sum(block.size for block in matcher.get_matching_blocks())
			total += max(len(mine), len(theirs))
	print(f'chapter 7: {same / total:.0%} of the remaster instructions found again (animations excepted)')


def main(scenario_dir: str, checking: bool):
	learned = learn(scenario_dir, conf.game_folder)
	learned.halves[PUMP] = PUMP_HALVES
	names = Names(learned)
	if checking:
		check(scenario_dir, learned, names)
	text = original.read(os.path.join(scenario_dir, SCENE + '.ks'))
	translator = Translator(learned, names, bg_layer=0, scales={PUMP: PUMP_SCALE})  # the script starts with black on layer 0
	out = translate(text, translator, get_file_lines(conf.script_source))
	missing = sorted({s for s in re.findall(r'storage=([^\s\]]+)', text)
	                  if not s.startswith(('se', 'm')) and s not in ('black', 'white') and not names.remaster(s)})
	if missing:
		print('images not in the remaster:', ', '.join(missing))
	with open(INSTRUCTIONS, 'w', encoding='utf-8', newline='\n') as f:
		for item in out:
			f.write(json.dumps(['text', item[1], item[2]] if item[0] == 'text' else [item[0], *item[1]],
			                   ensure_ascii=False) + '\n')
	print(f'{INSTRUCTIONS}: {len(out)} instructions')


if __name__ == '__main__':
	if len(sys.argv) < 2:
		sys.exit(__doc__)
	main(sys.argv[1], '--check' in sys.argv[2:])

from sys import platform
import eel
from py_src.contrib.replace_in_file import findFileRe, replaceInfile
import translate


def start_eel(develop):
	"""Start Eel with either production or development configuration."""

	if develop:
		directory = 'web_src'
		app = None
		page = {'port': 5173}
		eel_port = 5169
	else:
		directory = 'dist_vite'
		app = 'chrome'
		page = 'index.html'

		# find a unused port to host the eel server/websocket
		# eel_port = find_unused_port()

		# replace the port in the web files
		replace_file = findFileRe("./dist_vite/assets", "index.*.js")
		replaceInfile(f"./dist_vite/assets/{replace_file}", 'ws://localhost:....', f"ws://localhost:{eel_port}")
		replaceInfile("./dist_vite/index.html", 'http://localhost:.....eel.js', f"http://localhost:{eel_port}/eel.js")



	eel.init(directory, ['.tsx', '.ts', '.jsx', '.js', '.html'])

	# These will be queued until the first connection is made, but won't be repeated on a page reload
	translate.init_translate()
	# say_hello_py('Python World!')
	# eel.say_hello_js('Python World!')   # Call a JavaScript function (must be after `eel.init()`)

	# eel.show_log('https://github.com/samuelhwilliams/Eel/issues/363 (show_log)')

	eel_kwargs = dict(
		host='localhost',
		port=eel_port,
		size=(1280, 800),
	)
	try:
		eel.start(page, mode=app, **eel_kwargs)

	except EnvironmentError:
		# If Chrome isn't found, fallback to Microsoft Edge on Win10 or greater
		if sys.platform in ['win32', 'win64'] and int(platform.release()) >= 10:
			eel.start(page, mode='edge', **eel_kwargs)
		else:
			raise


if __name__ == '__main__':
	import sys

	# Pass any second argument to enable debugging
	start_eel(develop=len(sys.argv) == 2)
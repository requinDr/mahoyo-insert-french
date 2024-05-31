import { useState } from 'react'
import './styles/App.scss'
import './styles/styles.scss'
import Logo from './assets/logo.png'
import Config from './screens/Config';
import Translate from './screens/Translate';

// Point Eel web socket to the instance
declare const window: any;
export const eel = window.eel
eel.set_host('ws://localhost:5169')

enum Pages {
	CONFIG = 'config',
	TRANSLATE = 'translate',
}

function App() {
	const [page, setPage] = useState<Pages>(Pages.TRANSLATE)

  return (  
    <div className="App">
      <header>
    		<img src={Logo} alt="logo" className="logo" />

				<nav>
					<button onClick={() => setPage(Pages.TRANSLATE)} className={`menu-item ${page === Pages.TRANSLATE ? 'active' : ''}`}>
						Translate
					</button>
					<button onClick={() => setPage(Pages.CONFIG)} className={`menu-item ${page === Pages.CONFIG ? 'active' : ''}`}>
						Config
					</button>
				</nav>
    	</header>

			<main>
				{page === Pages.TRANSLATE ?
					<Translate />
					:
					<Config />
				}
			</main>
    </div>
  )
}

export default App
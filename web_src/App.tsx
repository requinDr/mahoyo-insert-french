import { useState } from 'react'
import './styles/App.css'
import './styles/styles.css'
import Logo from './assets/logo.png'

// Point Eel web socket to the instance
declare const window: any;
export const eel = window.eel
eel.set_host( 'ws://localhost:5169' )

const start = async () => {
	eel.generate_translation();
}

function App() {
  const [label, setLabel] = useState('Processing')
  const [progress, setProgress] = useState(0)

  window.eel.expose(update_progress_js, 'update_progress_js')
  function update_progress_js(percentage: number, label: string) {
    setProgress(percentage)
    setLabel(label)
  }

  return (  
    <div className="App">
      <header>
    		<img src={Logo} alt="logo" className="logo" />
    	</header>
    	
    	<section className="main">
    		<button id="btn" onClick={start}>
    			Update translation
    		</button>

    		<h1 id="label">{label}</h1>
    		<div className="progressBar">
    			<div className="progress" style={{width: `${progress}%`}}></div>
    		</div>
    		<p id="percent">{progress}%</p>
    	</section>
    </div>
  )
}

export default App
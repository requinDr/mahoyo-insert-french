import { useState } from "react"
import { eel } from "../App"

const start = async () => {
	eel.generate_translation()
}

const Translate = () => {
  const [label, setLabel] = useState<string>('Processing')
  const [progress, setProgress] = useState<number>(0)

  eel.expose(update_progress_js, 'update_progress_js')
  function update_progress_js(percentage: number, label: string) {
    setProgress(percentage)
    setLabel(label)
  }
	
	return (
		<section className="main">
			<button onClick={start} className="main-button">
				Update translation
			</button>

			<h1 id="label">{label}</h1>
			<div className="progressBar">
				<div className="progress" style={{width: `${progress}%`}}></div>
			</div>
			<p id="percent">{progress}%</p>
		</section>
	)
}

export default Translate;
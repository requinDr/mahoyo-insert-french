import { memo, useEffect, useState } from "react"
import { eel } from "../App"
import InputText from "../components/InputText"

export type Config = Partial<{
	ks_source: string
	ks_translated: string
	script_source: string
	script_source_indent: string

	csv: {
		source: string
		generated: string
		create_csv: boolean
	}

	steam: {
		hfa_name: string
		source_folder: string
		output_folder: string
		swap_characters: boolean
	}

	switch: {
		output_folder: string
	}
}>

const get_config = async () => {
	eel.get_config()
}


const Config = () => {
	const [config, setConfig] = useState<Config>()

	useEffect(() => {
		get_config()
	}, [])

  eel.expose(update_conf_js, 'update_conf_js')
  function update_conf_js(conf: any) {
    setConfig(conf)
  }

	// function update_ini_config() {
	// 	eel.update_config(config)
	// }
	
	useEffect(() => {
		if (config !== undefined) {
			eel.update_config(config)
		}
	}, [config])

	return (
		<div>
			<InputText
				label="Japanese .ks folder"
				value={config?.ks_source || ''}
				onChange={(value) => setConfig(prev => ({...prev, ks_source: value}))}
			/>

			<InputText
				label="Translated .ks folder"
				value={config?.ks_translated || ''}
				onChange={(value) => console.log(value)}
			/>
		</div>
	)
}

export default  memo(Config);
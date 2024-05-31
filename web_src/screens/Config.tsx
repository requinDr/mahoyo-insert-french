import { memo, useEffect, useState } from "react"
import { eel } from "../App"
import InputText from "../components/InputText"

export type Config = Partial<{
	ks_source: string
	ks_translated: string
	script_source: string
	script_source_indent: string
	generated_translation: string

	csv: Partial<{
		source: string
		generated: string
		create_csv: boolean
	}>

	steam: Partial<{
		source_folder: string
		output_folder: string
		swap_characters: boolean
	}>

	switch: Partial<{
		output_folder: string
	}>
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
				onChange={(value) => setConfig(prev => ({...prev, ks_translated: value}))}
			/>

			<InputText
				label="Source script folder"
				value={config?.script_source || ''}
				onChange={(value) => setConfig(prev => ({...prev, script_source: value}))}
			/>

			<InputText
				label="CSV source"
				value={config?.csv?.source || ''}
				onChange={(value) => setConfig(prev => ({...prev, csv: {...prev?.csv, source: value}}))}
			/>

			<h2>Steam</h2>
			<InputText
				label="WITCH ON THE HOLY NIGHT folder"
				value={config?.steam?.source_folder || ''}
				onChange={(value) => setConfig(prev => (
					{
						...prev,
						steam: {
							...prev?.steam,
							source_folder: value
						}
					}
				))}
			/>

			<InputText
				label="Output patch folder"
				value={config?.steam?.output_folder || ''}
				onChange={(value) => setConfig(prev => (
					{
						...prev,
						steam: {
							...prev?.steam,
							output_folder: value
						}
					}
				))}
			/>

			<label>Swap characters</label>
			<input type="checkbox" checked={config?.steam?.swap_characters} onChange={(e) => setConfig(prev => (
				{
					...prev,
					steam: {
						...prev?.steam,
						swap_characters: e.target.checked
					}
				}
			))} />

			<h2>Switch</h2>
			<InputText
				label="Output patch folder"
				value={config?.switch?.output_folder || ''}
				onChange={(value) => setConfig(prev => (
					{
						...prev,
						switch: {
							...prev?.switch,
							output_folder: value
						}
					}
				))}
			/>
		</div>
	)
}

export default  memo(Config);
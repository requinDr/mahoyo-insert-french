type Props = {
	label: string
	value?: string
	onChange: (value: string) => void
}

const InputText = ({ label, value, onChange }: Props) => {
	return (
		<div className="input-text-container">
			<label>{label}</label>
			<input
				type="text"
				value={value}
				onChange={(e) => onChange(e.target.value)}
			/>
		</div>
	)
}

export default InputText
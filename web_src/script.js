const start = async () => {
	// eel.generate_translation();
	window.eel(generate_translation, 'generate_translation')
}

// eel.expose(update_progress_js);
eel.expose(update_progress_js);
function update_progress_js(percentage, label) {
	console.log(percentage, label);
	document.getElementById('label').innerText = label;
	document.getElementById('progress').style.width = percentage + '%';
	document.getElementById('percent').innerText = percentage + '%';
}
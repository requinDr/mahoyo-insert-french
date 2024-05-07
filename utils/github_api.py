import base64
import requests


def get_content_from_github(url: str):
	try:
		# Faire la requête GET à l'API GitHub
		response = requests.get(url)
		response.raise_for_status()  # Raise an exception for 4xx and 5xx status codes

		# Extraire le contenu encodé en base64
		content_base64 = response.json()["content"]

		# Décoder le contenu en base64
		content = base64.b64decode(content_base64).decode("utf-8")
		return content
	except Exception as e:
		print(f"Erreur lors de la lecture de l'URL {url} via l'API GitHub : {e}")
		return None

def is_github_url(url: str):
	if url.startswith("https://api.github.com/"):
		return True
	else:
		return False
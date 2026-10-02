"""Effects around letters (glow, shadow, outline), measured on the English text, and
compositing. Opacities are 0-1 arrays; images are float RGBA arrays (0-255)."""
import numpy as np
from scipy import ndimage


def ring(mask: np.ndarray, inner: int, outer: int) -> np.ndarray:
	"""Pixels between inner and outer pixels away from mask."""
	inside = ndimage.binary_dilation(mask, iterations=inner) if inner else mask
	return ndimage.binary_dilation(mask, iterations=outer) & ~inside


def fit_blur(letters: np.ndarray, opacity: np.ndarray, around: np.ndarray, sigmas=np.arange(1.0, 12.0, 0.5)):
	"""Glow or soft shadow of the English letters as (sigma, strength), such that on the
	pixels `around` them, opacity ≈ strength × gaussian_blur(letters, sigma)."""
	core = letters.astype(float)
	best = None
	for sigma in sigmas:
		blurred = ndimage.gaussian_filter(core, sigma)[around]
		strength = (opacity[around] * blurred).sum() / max((blurred ** 2).sum(), 1e-6)
		error = ((opacity[around] - strength * blurred) ** 2).mean()
		if best is None or error < best[0]:
			best = (error, sigma, strength)
	return best[1], best[2]


def blur(letters: np.ndarray, sigma: float, strength: float) -> np.ndarray:
	return np.clip(ndimage.gaussian_filter(letters, sigma) * strength, 0, 1)


def fit_outline(letters: np.ndarray, opacity: np.ndarray) -> tuple[float, float]:
	"""Solid outline of the English letters as (radius, opacity): the opacity is constant
	around the letters, then drops at the radius."""
	distance = ndimage.distance_transform_edt(~letters)
	profile = [(r, opacity[(distance > r - 0.25) & (distance <= r)].mean()) for r in np.arange(0.5, 20, 0.25)
	           if ((distance > r - 0.25) & (distance <= r)).any()]
	level = np.median([a for r, a in profile if 2 <= r <= 4])
	radius = next(r for r, a in profile if r > 2 and a < level / 2)
	return radius, level


def outline(letters: np.ndarray, radius: float, level: float) -> np.ndarray:
	distance = ndimage.distance_transform_edt(letters < 0.5)
	return np.clip(radius - distance, 0, 1) * level


def over(base: np.ndarray, color, alpha: np.ndarray) -> np.ndarray:
	"""Composites a color (RGB triple or image) with the opacity alpha over base."""
	a = alpha[..., None]
	base_alpha = base[..., 3:] / 255
	out_alpha = a + base_alpha * (1 - a)
	rgb = (np.asarray(color, float) * a + base[..., :3] * base_alpha * (1 - a)) / np.maximum(out_alpha, 1e-6)
	return np.concatenate([rgb, out_alpha * 255], -1)


def over_image(base: np.ndarray, top: np.ndarray) -> np.ndarray:
	return over(base, top[..., :3], top[..., 3] / 255)

def ks_name_to_switch_name(ks_name: str) -> str:
	return ks_name[:-3].replace("-", "_").replace(".", "DOT").upper() + ".txt"
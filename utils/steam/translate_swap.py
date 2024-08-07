# Define characters position and width
chars_width: dict[str, int] = {
  ' ':26, '!':21, '"':27, '#':45, '$':45, '%':65, '&':52, "'":17, '(':27, ')':27, '*':33, '+':45, ',':21, '-':31,
  '.':21, '/':37, '0':43, '1':30, '2':43, '3':44, '4':44, '5':44, '6':43, '7':43, '8':43, '9':44, ':':21, ';':21,
  '<':45, '=':45, '>':45, '?':41, '@':59, 'A':55, 'B':49, 'C':54, 'D':51, 'E':45, 'F':43, 'G':55, 'H':49, 'I':19,
  'J':40, 'K':51, 'L':43, 'M':59, 'N':49, 'O':57, 'P':47, 'Q':57, 'R':50, 'S':49, 'T':49, 'U':49, 'V':53, 'W':67,
  'X':53, 'Y':55, 'Z':49, '[':25,'\\':37, ']':25, '^':45, '_':45, '`':26, 'a':44, 'b':45, 'c':43, 'd':45, 'e':44,
  'f':32, 'g':43, 'h':41, 'i':19, 'j':24, 'k':42, 'l':19, 'm':59, 'n':41, 'o':45, 'p':45, 'q':45, 'r':31, 's':41,
  't':31, 'u':41, 'v':43, 'w':59, 'x':45, 'y':43, 'z':41, '{':30, '|':17, '}':30, '~':43, '±':45, '·':21, '×':43,

  'à':44, 'è':44, 'ì':19, 'ò':45, 'ù':41, 'ỳ':43, 'á':44, 'é':44, 'í':19, 'ó':45, 'ú':41, 'ý':43, 'æ':58, 'œ':60,
  'â':44, 'ê':44, 'î':24, 'ô':45, 'û':41, 'ŷ':43, 'ä':44, 'ë':44, 'ï':24, 'ö':45, 'ü':41, 'ÿ':43, 'ç':43, 'ß':35,
  'ā':44, 'ē':44, 'ī':24, 'ō':45, 'ū':41, 'å':44, 'ñ':41, '❶':26, '❷':26, '❸':26, '❹':26, '❺':26, '❻':26, '❼':26,
  'À':55, 'È':45, 'Ì':19, 'Ò':57, 'Ù':49, 'Ỳ':55, 'Á':55, 'É':45, 'Í':19, 'Ó':57, 'Ú':49, 'Ý':55, 'Æ':65, 'Œ':71,
  'Â':55, 'Ê':45, 'Î':24, 'Ô':57, 'Û':49, 'Ŷ':55, 'Ä':55, 'Ë':45, 'Ï':24, 'Ö':57, 'Ü':49, 'Ÿ':55, 'Ç':55, '❽':26,
  'Ā':55, 'Ē':45, 'Ī':24, 'Ō':57, 'Ū':49, 'Å':55, 'Ñ':49, '❾':26, '❿':26, '⓫':26, '⓬':26, '⓭':26, '⓮':26, '⓯':26,
  '÷':45, '¡':21, '¿':41, '「':73, '」':73, '『':73, '』':73, '«': 43, '»': 43, 'ー': 73, '²': 28,

  '■': 73, '―': 73, '…': 73, '“': 43, '”': 43, '—': 73, "’": 73
}

# Swap extended latin characters with special 1-byte characters
char_swap_dict: dict[str, str] = {
  # 'À' : None,
  # 'Ç' : None # might be necessary
  # 'È' : None, # max column is 42
    'É' : 'W',
  # 'Œ' : 'Oe',
  # 'Â' : None, # might be necessary
  # 'Ê' : None,
  # 'Î' : None,
    'à' : '#',
    'è' : '$',
    'ù' : '+',
    'é' : '=',
    'â' : 'X',
    'ê' : '_',
    'î' : '`',
    'ô' : '&',
    'û' : ';',
    # 'ë' : ':',
    'ï' : '{',
    'ç' : '}',
    'ō' : '*',
    'ū' : 'Z',
    # '²' : '2',
}

replace_dict: dict[str, str] = {
  'Œ' : 'Oe',
  'œ' : 'oe',
}

# Swap all characters in line
def swap_char_in_line(ligne: str):
  for (k, v) in char_swap_dict.items():
    if k in ligne:
      if v in ligne:
        temp_char = chr(ord('a') + ord(k))
        ligne = ligne.replace(k, temp_char)\
                     .replace(v, k)\
                     .replace(temp_char, v)
      else:
        ligne = ligne.replace(k, v)
    elif v in ligne:
      ligne = ligne.replace(v, k)
  return ligne

def replace_chars(ligne: str):
  for (k, v) in replace_dict.items():
    ligne = ligne.replace(k, v)
  return ligne

# Swap all characters in script file
def swap_char_in_script(lignes_script: list[str]):
  for i in range(len(lignes_script)):
    lignes_script[i] = swap_char_in_line(lignes_script[i])
    lignes_script[i] = replace_chars(lignes_script[i])
  return lignes_script

def line_char_length(ligne: str):
  length = 0
  for char in ligne:
    length += chars_width[char] if char in chars_width else 73

  return length
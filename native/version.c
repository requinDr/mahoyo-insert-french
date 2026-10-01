/*
 * Faux version.dll chargé automatiquement par WoH.exe depuis le dossier du jeu.
 * Il applique la traduction française en mémoire, sans modifier aucun fichier :
 *  - les noms de ressources anglaises (script_text_en.ctd, *_en.cbg, polices...)
 *    sont redirigés vers leurs équivalents français présents dans data00999.hfa ;
 *  - les textes système (ressource TEXT/5) sont lus depuis data00999.hfa ;
 *  - le titre de la fenêtre se termine par « - Patch FR » ;
 *  - les lettres accentuées font partie des mots comme l'ASCII : plus de retour
 *    à la ligne au milieu d'un mot, et même espacement que les autres lettres.
 * Les fonctions de version.dll sont transmises à la vraie DLL système.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <string.h>

#define ARCHIVE_NAME L"data00999.hfa"
#define TEXT5_ENTRY "TEXT5_fr.csv"
#define HFA_NAME_SIZE 96
#define HFA_ENTRY_SIZE 128

/* ---------- Transmission vers le vrai version.dll ---------- */

static HMODULE system_version(void) {
    static HMODULE module;
    if (!module) {
        wchar_t path[MAX_PATH];
        UINT length = GetSystemDirectoryW(path, MAX_PATH);
        if (length == 0 || length > MAX_PATH - 16) return NULL;
        wcscpy_s(path + length, MAX_PATH - length, L"\\version.dll");
        module = LoadLibraryW(path);
    }
    return module;
}

/* Toutes les fonctions de version.dll prennent au plus 8 arguments entiers. */
typedef INT_PTR (WINAPI *forward_t)(INT_PTR, INT_PTR, INT_PTR, INT_PTR, INT_PTR, INT_PTR, INT_PTR, INT_PTR);
#define FORWARD(name)                                                                   \
    INT_PTR WINAPI proxy_##name(INT_PTR a, INT_PTR b, INT_PTR c, INT_PTR d,             \
                                INT_PTR e, INT_PTR f, INT_PTR g, INT_PTR h) {           \
        static forward_t target;                                                        \
        if (!target) target = (forward_t)GetProcAddress(system_version(), #name);       \
        if (!target) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }                  \
        return target(a, b, c, d, e, f, g, h);                                          \
    }
FORWARD(GetFileVersionInfoA)
FORWARD(GetFileVersionInfoByHandle)
FORWARD(GetFileVersionInfoExA)
FORWARD(GetFileVersionInfoExW)
FORWARD(GetFileVersionInfoSizeA)
FORWARD(GetFileVersionInfoSizeExA)
FORWARD(GetFileVersionInfoSizeExW)
FORWARD(GetFileVersionInfoSizeW)
FORWARD(GetFileVersionInfoW)
FORWARD(VerFindFileA)
FORWARD(VerFindFileW)
FORWARD(VerInstallFileA)
FORWARD(VerInstallFileW)
FORWARD(VerLanguageNameA)
FORWARD(VerLanguageNameW)
FORWARD(VerQueryValueA)
FORWARD(VerQueryValueW)

/* ---------- Archive française ---------- */

static char (*archive_names)[HFA_NAME_SIZE];
static DWORD archive_count;
static BYTE *text5;
static DWORD text5_size;

static BOOL read_exact(HANDLE file, void *buffer, DWORD size) {
    DWORD read = 0;
    return ReadFile(file, buffer, size, &read, NULL) && read == size;
}

static BOOL load_archive(void) {
    wchar_t path[MAX_PATH];
    DWORD length = GetModuleFileNameW(NULL, path, MAX_PATH);
    if (length == 0 || length >= MAX_PATH) return FALSE;
    wchar_t *slash = wcsrchr(path, L'\\');
    if (!slash || slash + 1 + wcslen(ARCHIVE_NAME) >= path + MAX_PATH) return FALSE;
    wcscpy_s(slash + 1, MAX_PATH - (slash + 1 - path), ARCHIVE_NAME);

    HANDLE file = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, 0, NULL);
    if (file == INVALID_HANDLE_VALUE) return FALSE;
    BOOL success = FALSE;
    BYTE header[16];
    BYTE *table = NULL;
    if (!read_exact(file, header, sizeof(header)) || memcmp(header, "HUNEXGGEFA10", 12) != 0) goto done;
    DWORD count;
    memcpy(&count, header + 12, sizeof(count));
    if (count == 0 || count > 100000) goto done;
    table = HeapAlloc(GetProcessHeap(), 0, (SIZE_T)count * HFA_ENTRY_SIZE);
    archive_names = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)count * HFA_NAME_SIZE);
    if (!table || !archive_names || !read_exact(file, table, count * HFA_ENTRY_SIZE)) goto done;
    const DWORD data_start = 16 + count * HFA_ENTRY_SIZE;
    for (DWORD i = 0; i < count; ++i) {
        const BYTE *entry = table + (SIZE_T)i * HFA_ENTRY_SIZE;
        memcpy(archive_names[i], entry, HFA_NAME_SIZE - 1);
        if (strcmp(archive_names[i], TEXT5_ENTRY) == 0) {
            DWORD offset, size;
            memcpy(&offset, entry + HFA_NAME_SIZE, 4);
            memcpy(&size, entry + HFA_NAME_SIZE + 4, 4);
            LARGE_INTEGER position;
            position.QuadPart = (LONGLONG)data_start + offset;
            text5 = HeapAlloc(GetProcessHeap(), 0, size ? size : 1);
            if (!text5 || !SetFilePointerEx(file, position, NULL, FILE_BEGIN) || !read_exact(file, text5, size)) goto done;
            text5_size = size;
        }
    }
    archive_count = count;
    success = TRUE;
done:
    if (table) HeapFree(GetProcessHeap(), 0, table);
    CloseHandle(file);
    return success;
}

static BOOL archive_contains(const char *name) {
    for (DWORD i = 0; i < archive_count; ++i)
        if (_stricmp(archive_names[i], name) == 0) return TRUE;
    return FALSE;
}

/* ---------- Image du jeu ---------- */

static BYTE *game;

static IMAGE_NT_HEADERS64 *nt_headers(void) {
    return (IMAGE_NT_HEADERS64 *)(game + ((IMAGE_DOS_HEADER *)game)->e_lfanew);
}

static IMAGE_SECTION_HEADER *section(const char *name) {
    IMAGE_NT_HEADERS64 *nt = nt_headers();
    IMAGE_SECTION_HEADER *sections = IMAGE_FIRST_SECTION(nt);
    for (WORD i = 0; i < nt->FileHeader.NumberOfSections; ++i)
        if (strncmp((const char *)sections[i].Name, name, IMAGE_SIZEOF_SHORT_NAME) == 0) return &sections[i];
    return NULL;
}

static void write_memory(void *address, const void *data, SIZE_T size) {
    DWORD protection;
    if (!VirtualProtect(address, size, PAGE_EXECUTE_READWRITE, &protection)) return;
    memcpy(address, data, size);
    VirtualProtect(address, size, protection, &protection);
    FlushInstructionCache(GetCurrentProcess(), address, size);
}

/* ---------- Césure et espacement : le latin est traité comme l'ASCII ---------- */

/* Le moteur (version Steam 1.1, horodatage 0x658e4f20) découpe les lignes en
 * mots composés uniquement d'ASCII imprimable : toute lettre accentuée termine
 * le mot, d'où des coupures comme « vé|ritable ». Cette fonction est remplacée. */
static const BYTE original_copy_word[] = {
    0x48, 0x89, 0x5c, 0x24, 0x08, 0x33, 0xdb, 0x4c, 0x8b, 0xd9, 0x44, 0x8b, 0xd3, 0x48, 0x2b, 0xd1,
    0x48, 0x8b, 0xc1, 0x0f, 0x1f, 0x40, 0x00, 0x66, 0x0f, 0x1f, 0x84, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x44, 0x0f, 0xb7, 0x0c, 0x02, 0x45, 0x8d, 0x41, 0xdf, 0x66, 0x41, 0x83, 0xf8, 0x1a, 0x76, 0x0a,
    0x41, 0x8d, 0x49, 0xc3, 0x66, 0x83, 0xf9, 0x41, 0x77, 0x0d, 0x41, 0xff, 0xc2, 0x66, 0x44, 0x89,
    0x08, 0x48, 0x83, 0xc0, 0x02, 0xeb, 0xd9, 0x49, 0x63, 0xca, 0x41, 0x8b, 0xc2, 0x66, 0x41, 0x89,
    0x1c, 0x4b, 0x48, 0x8b, 0x5c, 0x24, 0x08, 0xc3,
};

static BOOL is_word_character(uint16_t c) {
    if (c >= 0x21 && c <= 0x7e) return c != '<';  /* règle d'origine ; '<' ouvre une balise */
    if (c >= 0xa0 && c <= 0x24f) return TRUE;     /* latin étendu */
    return c >= 0x2018 && c <= 0x201f;            /* guillemets et apostrophes typographiques */
}

/* Même convention d'appel que l'original : copie le mot de `text` dans `word`. */
static int copy_word(uint16_t *word, const uint16_t *text) {
    int length = 0;
    while (is_word_character(text[length])) {
        word[length] = text[length];
        ++length;
    }
    word[length] = 0;
    return length;
}

/* Espacement des lettres : le moteur applique celui des idéogrammes à partir de
 * U+0080. Le seuil passe à U+0250, à l'identique dans la mesure et le rendu. */
static const BYTE measure_spacing_before[] = {0x81, 0xff, 0x80, 0x00, 0x00, 0x00,        /* cmp edi, 0x80 */
                                              0x73, 0x07, 0xf3, 0x0f, 0x10, 0x70, 0x64};
static const BYTE measure_spacing_after[] = {0x81, 0xff, 0x50, 0x02, 0x00, 0x00,         /* cmp edi, 0x250 */
                                             0x73, 0x07, 0xf3, 0x0f, 0x10, 0x70, 0x64};
static const BYTE render_spacing_before[] = {0x41, 0x81, 0xfd, 0x80, 0x00, 0x00, 0x00,   /* cmp r13d, 0x80 */
                                             0x73, 0x07, 0xf3, 0x0f, 0x10, 0x4f, 0x64};
static const BYTE render_spacing_after[] = {0x41, 0x81, 0xfd, 0x50, 0x02, 0x00, 0x00,    /* cmp r13d, 0x250 */
                                            0x73, 0x07, 0xf3, 0x0f, 0x10, 0x4f, 0x64};

typedef struct { const BYTE *before; const BYTE *after; size_t size; BYTE *address; } code_patch;
static code_patch code_patches[] = {
    {original_copy_word, NULL, sizeof(original_copy_word), NULL},  /* redirigé vers copy_word */
    {measure_spacing_before, measure_spacing_after, sizeof(measure_spacing_before), NULL},
    {render_spacing_before, render_spacing_after, sizeof(render_spacing_before), NULL},
};

static BYTE *find_unique(const BYTE *pattern, size_t size) {
    IMAGE_SECTION_HEADER *text = section(".text");
    if (!text || text->Misc.VirtualSize < size) return NULL;
    BYTE *start = game + text->VirtualAddress;
    BYTE *end = start + text->Misc.VirtualSize - size;
    BYTE *found = NULL;
    for (BYTE *p = start; p <= end; ++p) {
        if (*p == pattern[0] && memcmp(p, pattern, size) == 0) {
            if (found) return NULL;  /* ambigu : version inconnue */
            found = p;
        }
    }
    return found;
}

/* Vrai si le code du jeu est déchiffré et correspond à la version prise en charge. */
static BOOL find_code_patches(void) {
    for (size_t i = 0; i < ARRAYSIZE(code_patches); ++i) {
        code_patches[i].address = find_unique(code_patches[i].before, code_patches[i].size);
        if (!code_patches[i].address) return FALSE;
    }
    return TRUE;
}

static void apply_code_patches(void) {
    for (size_t i = 0; i < ARRAYSIZE(code_patches); ++i) {
        if (code_patches[i].after) {
            write_memory(code_patches[i].address, code_patches[i].after, code_patches[i].size);
        } else {
            BYTE jump[14] = {0xff, 0x25, 0, 0, 0, 0};  /* jmp qword ptr [rip] */
            void *target = (void *)copy_word;
            memcpy(jump + 6, &target, sizeof(target));
            write_memory(code_patches[i].address, jump, sizeof(jump));
        }
    }
}

/* ---------- Redirection des noms de ressources ---------- */

/* Ressources communes à toutes les langues, remplacées par un nom de même longueur. */
static const char *const shared_names[][2] = {
    {"mode1.cbg", "modfr.cbg"},  /* noms des langues dans les paramètres : « Français » */
};

/* script_text_en.ctd -> script_text_fr.ctd, FONT_en_H00.mzp -> FONT_fr_H00.mzp,
 * Font010000.ccit -> Font040000.ccit... uniquement si l'archive contient le résultat. */
static BOOL french_name(const wchar_t *name, size_t length, char *result) {
    if (length >= HFA_NAME_SIZE) return FALSE;
    for (size_t i = 0; i < length; ++i) {
        if (name[i] < 0x20 || name[i] > 0x7e) return FALSE;
        result[i] = (char)name[i];
    }
    result[length] = 0;
    for (size_t i = 0; i < ARRAYSIZE(shared_names); ++i) {
        if (strcmp(result, shared_names[i][0]) == 0) {
            strcpy_s(result, HFA_NAME_SIZE, shared_names[i][1]);
            return archive_contains(result);
        }
    }
    BOOL changed = FALSE;
    if (strncmp(result, "Font010", 7) == 0) {
        result[5] = '4';
        changed = TRUE;
    }
    for (char *p = result; (p = strstr(p, "_en")) != NULL; p += 3) {
        if (p[3] == '_' || p[3] == '.') {
            p[1] = 'f';
            p[2] = 'r';
            changed = TRUE;
        }
    }
    return changed && archive_contains(result);
}

static int redirect_names(void) {
    IMAGE_SECTION_HEADER *rdata = section(".rdata");
    if (!rdata) return 0;
    wchar_t *strings = (wchar_t *)(game + rdata->VirtualAddress);
    const size_t count = rdata->Misc.VirtualSize / sizeof(wchar_t);
    int redirected = 0;
    size_t i = 1;
    while (i < count) {
        if (strings[i] == 0 || strings[i - 1] != 0) { ++i; continue; }
        size_t end = i;
        while (end < count && strings[end] != 0 && end - i < HFA_NAME_SIZE) ++end;
        if (end < count && strings[end] == 0) {
            char name[HFA_NAME_SIZE];
            if (end - i == 3 && wcsncmp(strings + i, L"_en", 3) == 0) {
                /* Suffixe utilisé pour composer certains noms (popup, teatime...). */
                write_memory(strings + i, L"_fr", 3 * sizeof(wchar_t));
                ++redirected;
            } else if (french_name(strings + i, end - i, name)) {
                wchar_t wide[HFA_NAME_SIZE];
                for (size_t k = 0; k < end - i; ++k) wide[k] = (wchar_t)(unsigned char)name[k];
                write_memory(strings + i, wide, (end - i) * sizeof(wchar_t));
                ++redirected;
            }
        }
        i = end + 1;
    }
    return redirected;
}

/* ---------- Activation ---------- */

static INIT_ONCE activation = INIT_ONCE_STATIC_INIT;
static BOOL french_active;

static void warn(const wchar_t *message) {
    MessageBoxW(NULL, message, L"Patch français Mahoyo", MB_OK | MB_ICONWARNING);
}

/* Le code du jeu est chiffré par Steam jusqu'au point d'entrée : on attend qu'il
 * soit lisible. `final` indique que le jeu ouvre ses archives, donc que le code
 * devrait l'être ; si le code attendu reste introuvable, la version n'est pas gérée. */
static BOOL CALLBACK activate(PINIT_ONCE once, PVOID final, PVOID *context) {
    (void)once; (void)context;
    if (!find_code_patches()) {
        if (!final) return FALSE;  /* réessayer au prochain appel */
        warn(L"Cette version du jeu n'est pas prise en charge par le patch français.\n"
             L"Le jeu va démarrer en anglais. Une mise à jour du patch est nécessaire.");
        return TRUE;
    }
    if (!load_archive()) {
        warn(L"Fichier " ARCHIVE_NAME L" introuvable ou illisible.\n"
             L"Le jeu va démarrer sans le patch français.");
        return TRUE;
    }
    if (redirect_names() == 0) {
        warn(L"Aucune ressource française trouvée dans " ARCHIVE_NAME L".");
        return TRUE;
    }
    apply_code_patches();
    french_active = TRUE;
    return TRUE;
}

static void try_activate(BOOL final) {
    InitOnceExecuteOnce(&activation, activate, (PVOID)(INT_PTR)final, NULL);
}

static BOOL is_archive_path(const wchar_t *path) {
    if (!path) return FALSE;
    size_t length = wcslen(path);
    return length >= 4 && _wcsicmp(path + length - 4, L".hfa") == 0;
}

/* ---------- Fonctions du jeu interceptées ---------- */

static HANDLE (WINAPI *real_FindFirstFileW)(LPCWSTR, LPWIN32_FIND_DATAW);
static HANDLE (WINAPI *real_FindFirstFileExW)(LPCWSTR, FINDEX_INFO_LEVELS, LPVOID, FINDEX_SEARCH_OPS, LPVOID, DWORD);
static HANDLE (WINAPI *real_CreateFileW)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static HRSRC (WINAPI *real_FindResourceW)(HMODULE, LPCWSTR, LPCWSTR);
static HGLOBAL (WINAPI *real_LoadResource)(HMODULE, HRSRC);
static DWORD (WINAPI *real_SizeofResource)(HMODULE, HRSRC);
static LPVOID (WINAPI *real_LockResource)(HGLOBAL);

static HANDLE WINAPI hook_FindFirstFileW(LPCWSTR path, LPWIN32_FIND_DATAW data) {
    if (is_archive_path(path)) try_activate(TRUE);
    return real_FindFirstFileW(path, data);
}

static HANDLE WINAPI hook_FindFirstFileExW(LPCWSTR path, FINDEX_INFO_LEVELS level, LPVOID data,
                                           FINDEX_SEARCH_OPS search, LPVOID filter, DWORD flags) {
    if (is_archive_path(path)) try_activate(TRUE);
    return real_FindFirstFileExW(path, level, data, search, filter, flags);
}

static HANDLE WINAPI hook_CreateFileW(LPCWSTR path, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES security,
                                      DWORD disposition, DWORD flags, HANDLE template_file) {
    if (is_archive_path(path)) try_activate(TRUE);
    return real_CreateFileW(path, access, share, security, disposition, flags, template_file);
}

/* Ressource TEXT/5 : textes système (CSV ja,en,zc,zt ; le français est en colonne en). */
static const char text5_marker = 0;
#define TEXT5_HANDLE ((HRSRC)&text5_marker)

static HRSRC WINAPI hook_FindResourceW(HMODULE module, LPCWSTR name, LPCWSTR type) {
    try_activate(FALSE);
    if (french_active && text5 && (module == NULL || (BYTE *)module == game) &&
        IS_INTRESOURCE(name) && LOWORD((ULONG_PTR)name) == 5 &&
        !IS_INTRESOURCE(type) && _wcsicmp(type, L"TEXT") == 0)
        return TEXT5_HANDLE;
    return real_FindResourceW(module, name, type);
}

static HGLOBAL WINAPI hook_LoadResource(HMODULE module, HRSRC resource) {
    if (resource == TEXT5_HANDLE) return (HGLOBAL)text5;
    return real_LoadResource(module, resource);
}

static DWORD WINAPI hook_SizeofResource(HMODULE module, HRSRC resource) {
    if (resource == TEXT5_HANDLE) return text5_size;
    return real_SizeofResource(module, resource);
}

static LPVOID WINAPI hook_LockResource(HGLOBAL data) {
    if (data && data == (HGLOBAL)text5) return text5;
    return real_LockResource(data);
}

/* Titre de la fenêtre : « WITCH ON THE HOLY NIGHT ( ver 1.1 ) - Patch FR ». */
#define WINDOW_TITLE L"WITCH ON THE HOLY NIGHT"
#define TITLE_SUFFIX L" - Patch FR"

static HWND (WINAPI *real_CreateWindowExW)(DWORD, LPCWSTR, LPCWSTR, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, LPVOID);
static BOOL (WINAPI *real_SetWindowTextW)(HWND, LPCWSTR);
static HWND (WINAPI *real_FindWindowW)(LPCWSTR, LPCWSTR);

/* Renvoie `title` complété du suffixe dans `buffer`, ou `title` inchangé. */
static LPCWSTR french_title(LPCWSTR title, wchar_t *buffer, size_t size) {
    try_activate(FALSE);
    if (!french_active || !title || IS_INTRESOURCE(title) ||
        wcsncmp(title, WINDOW_TITLE, wcslen(WINDOW_TITLE)) != 0 || wcsstr(title, TITLE_SUFFIX) ||
        wcscpy_s(buffer, size, title) != 0 || wcscat_s(buffer, size, TITLE_SUFFIX) != 0)
        return title;
    return buffer;
}

static HWND WINAPI hook_CreateWindowExW(DWORD style_ex, LPCWSTR class_name, LPCWSTR title, DWORD style, int x, int y,
                                        int width, int height, HWND parent, HMENU menu, HINSTANCE instance, LPVOID param) {
    wchar_t buffer[256];
    return real_CreateWindowExW(style_ex, class_name, french_title(title, buffer, ARRAYSIZE(buffer)), style,
                                x, y, width, height, parent, menu, instance, param);
}

static BOOL WINAPI hook_SetWindowTextW(HWND window, LPCWSTR title) {
    wchar_t buffer[256];
    return real_SetWindowTextW(window, french_title(title, buffer, ARRAYSIZE(buffer)));
}

static HWND WINAPI hook_FindWindowW(LPCWSTR class_name, LPCWSTR title) {
    wchar_t buffer[256];
    return real_FindWindowW(class_name, french_title(title, buffer, ARRAYSIZE(buffer)));
}

static const struct { const char *module; const char *name; void **real; void *hook; } hooks[] = {
    {"kernel32.dll", "FindFirstFileW", (void **)&real_FindFirstFileW, (void *)hook_FindFirstFileW},
    {"kernel32.dll", "FindFirstFileExW", (void **)&real_FindFirstFileExW, (void *)hook_FindFirstFileExW},
    {"kernel32.dll", "CreateFileW", (void **)&real_CreateFileW, (void *)hook_CreateFileW},
    {"kernel32.dll", "FindResourceW", (void **)&real_FindResourceW, (void *)hook_FindResourceW},
    {"kernel32.dll", "LoadResource", (void **)&real_LoadResource, (void *)hook_LoadResource},
    {"kernel32.dll", "SizeofResource", (void **)&real_SizeofResource, (void *)hook_SizeofResource},
    {"kernel32.dll", "LockResource", (void **)&real_LockResource, (void *)hook_LockResource},
    {"user32.dll", "CreateWindowExW", (void **)&real_CreateWindowExW, (void *)hook_CreateWindowExW},
    {"user32.dll", "SetWindowTextW", (void **)&real_SetWindowTextW, (void *)hook_SetWindowTextW},
    {"user32.dll", "FindWindowW", (void **)&real_FindWindowW, (void *)hook_FindWindowW},
};

/* Remplace les entrées de la table d'imports de WoH.exe (pas celles des autres modules). */
static void hook_imports(void) {
    IMAGE_DATA_DIRECTORY *directory = &nt_headers()->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!directory->VirtualAddress) return;
    for (IMAGE_IMPORT_DESCRIPTOR *module = (IMAGE_IMPORT_DESCRIPTOR *)(game + directory->VirtualAddress);
         module->Name; ++module) {
        const char *module_name = (const char *)(game + module->Name);
        if (!module->OriginalFirstThunk) continue;
        IMAGE_THUNK_DATA64 *names = (IMAGE_THUNK_DATA64 *)(game + module->OriginalFirstThunk);
        IMAGE_THUNK_DATA64 *addresses = (IMAGE_THUNK_DATA64 *)(game + module->FirstThunk);
        for (; names->u1.AddressOfData; ++names, ++addresses) {
            if (IMAGE_SNAP_BY_ORDINAL64(names->u1.Ordinal)) continue;
            const char *name = ((IMAGE_IMPORT_BY_NAME *)(game + names->u1.AddressOfData))->Name;
            for (size_t i = 0; i < ARRAYSIZE(hooks); ++i) {
                if (_stricmp(module_name, hooks[i].module) != 0 || strcmp(name, hooks[i].name) != 0) continue;
                *hooks[i].real = (void *)addresses->u1.Function;
                ULONGLONG hook = (ULONGLONG)hooks[i].hook;
                write_memory(&addresses->u1.Function, &hook, sizeof(hook));
            }
        }
    }
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        DisableThreadLibraryCalls(instance);
        game = (BYTE *)GetModuleHandleW(NULL);
        for (size_t i = 0; i < ARRAYSIZE(hooks); ++i)
            *hooks[i].real = (void *)GetProcAddress(GetModuleHandleA(hooks[i].module), hooks[i].name);
        hook_imports();
    }
    return TRUE;
}

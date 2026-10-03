/*
 * Proxy version.dll, loaded by WoH.exe from the game folder. It applies the French
 * translation in memory, without changing any file:
 *  - the names of English resources (script_text_en.ctd, *_en.cbg, fonts...) are
 *    redirected to their French versions in data00999.hfa;
 *  - resources of other archives replaced by data00999.hfa are served from it;
 *  - the system texts (TEXT/5 resource) are read from data00999.hfa;
 *  - the window title ends with " - Patch FR";
 *  - .rdata replacements built with the patch (menu particles, line breaks);
 *  - accented letters are part of words like ASCII ones: no line break inside a word,
 *    and the same spacing as the other letters;
 *  - the labels of the settings sliders are drawn whole.
 * The version.dll functions are forwarded to the real system DLL.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define ARCHIVE_NAME L"data00999.hfa"
#define TEXT5_ENTRY "TEXT5_fr.csv"
#define DATA_PATCHES_ENTRY "rdata_fr.bin"  /* replacements in the engine data, built with the patch */
#define HFA_NAME_SIZE 96
#define HFA_ENTRY_SIZE 128

/* ---------- Forwarding to the real version.dll ---------- */

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

/* All the version.dll functions take at most 8 integer arguments. */
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

/* ---------- French archive ---------- */

/* Entries of data00999.hfa, sorted by name (the first field). An image shared by all
 * languages is a delta there (DELTA_MAGIC): only its changed tiles, the whole file being
 * rebuilt from the original of the game (see below). */
#define DELTA_MAGIC "MZPDELTA"
#define DELTA_HEADER_SIZE 18  /* magic, original size, result size, count of entries */
static struct archive_entry {
    char name[HFA_NAME_SIZE];
    DWORD offset, size;
    BOOL delta;
    DWORD original_size, result_size;  /* of a delta */
} *archive_entries;
static DWORD archive_count;
static HANDLE archive_file = INVALID_HANDLE_VALUE;  /* stays open to serve our files */
static DWORD archive_data_start;
static SRWLOCK archive_file_lock = SRWLOCK_INIT;
static BYTE *text5;
static DWORD text5_size;
static BYTE *data_patches;
static DWORD data_patches_size;

static BOOL read_exact(HANDLE file, void *buffer, DWORD size) {
    DWORD read = 0;
    return ReadFile(file, buffer, size, &read, NULL) && read == size;
}

static int compare_names(const void *a, const void *b) {
    return _stricmp((const char *)a, (const char *)b);
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
    archive_entries = HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, (SIZE_T)count * sizeof(*archive_entries));
    if (!table || !archive_entries || !read_exact(file, table, count * HFA_ENTRY_SIZE)) goto done;
    const DWORD data_start = 16 + count * HFA_ENTRY_SIZE;
    for (DWORD i = 0; i < count; ++i) {
        const BYTE *entry = table + (SIZE_T)i * HFA_ENTRY_SIZE;
        struct archive_entry *current = &archive_entries[i];
        memcpy(current->name, entry, HFA_NAME_SIZE - 1);
        memcpy(&current->offset, entry + HFA_NAME_SIZE, 4);
        memcpy(&current->size, entry + HFA_NAME_SIZE + 4, 4);
        BYTE **target = NULL;
        DWORD *target_size = NULL;
        if (current->size >= DELTA_HEADER_SIZE) {
            BYTE start[DELTA_HEADER_SIZE];
            LARGE_INTEGER position;
            position.QuadPart = (LONGLONG)data_start + current->offset;
            if (!SetFilePointerEx(file, position, NULL, FILE_BEGIN) || !read_exact(file, start, sizeof(start))) goto done;
            if (memcmp(start, DELTA_MAGIC, 8) == 0) {
                current->delta = TRUE;
                memcpy(&current->original_size, start + 8, 4);
                memcpy(&current->result_size, start + 12, 4);
            }
        }
        if (strcmp(current->name, TEXT5_ENTRY) == 0) {
            target = &text5;
            target_size = &text5_size;
        } else if (strcmp(current->name, DATA_PATCHES_ENTRY) == 0) {
            target = &data_patches;
            target_size = &data_patches_size;
        }
        if (target) {
            LARGE_INTEGER position;
            position.QuadPart = (LONGLONG)data_start + current->offset;
            *target = HeapAlloc(GetProcessHeap(), 0, current->size ? current->size : 1);
            if (!*target || !SetFilePointerEx(file, position, NULL, FILE_BEGIN) || !read_exact(file, *target, current->size)) goto done;
            *target_size = current->size;
        }
    }
    archive_count = count;
    qsort(archive_entries, archive_count, sizeof(*archive_entries), compare_names);
    archive_data_start = data_start;
    archive_file = file;
    success = TRUE;
done:
    if (table) HeapFree(GetProcessHeap(), 0, table);
    if (!success) CloseHandle(file);
    return success;
}

static const struct archive_entry *find_entry(const char *name) {
    return bsearch(name, archive_entries, archive_count, sizeof(*archive_entries), compare_names);
}

static BOOL archive_contains(const char *name) {
    return find_entry(name) != NULL;
}

/* ---------- Game image ---------- */

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

/* ---------- Line breaks and spacing: Latin letters handled like ASCII ---------- */

/* The engine (Steam version 1.1, timestamp 0x658e4f20) cuts lines into words made only
 * of printable ASCII: any accented letter ends the word, hence breaks like "vé|ritable".
 * This function is replaced. */
static const BYTE original_copy_word[] = {
    0x48, 0x89, 0x5c, 0x24, 0x08, 0x33, 0xdb, 0x4c, 0x8b, 0xd9, 0x44, 0x8b, 0xd3, 0x48, 0x2b, 0xd1,
    0x48, 0x8b, 0xc1, 0x0f, 0x1f, 0x40, 0x00, 0x66, 0x0f, 0x1f, 0x84, 0x00, 0x00, 0x00, 0x00, 0x00,
    0x44, 0x0f, 0xb7, 0x0c, 0x02, 0x45, 0x8d, 0x41, 0xdf, 0x66, 0x41, 0x83, 0xf8, 0x1a, 0x76, 0x0a,
    0x41, 0x8d, 0x49, 0xc3, 0x66, 0x83, 0xf9, 0x41, 0x77, 0x0d, 0x41, 0xff, 0xc2, 0x66, 0x44, 0x89,
    0x08, 0x48, 0x83, 0xc0, 0x02, 0xeb, 0xd9, 0x49, 0x63, 0xca, 0x41, 0x8b, 0xc2, 0x66, 0x41, 0x89,
    0x1c, 0x4b, 0x48, 0x8b, 0x5c, 0x24, 0x08, 0xc3,
};

static BOOL is_word_character(uint16_t c) {
    if (c >= 0x21 && c <= 0x7e) return c != '<';  /* original rule; '<' opens a tag */
    if (c >= 0xa0 && c <= 0x24f) return TRUE;     /* extended Latin */
    if (c >= 0x2014 && c <= 0x2015) return TRUE;  /* long dashes — ― stay with the word */
    if (c >= 0x2018 && c <= 0x201f) return TRUE;  /* typographic quotes and apostrophes */
    return c >= 0x300c && c <= 0x300f;            /* 「」『』 stay with the next word */
}

/* French punctuation after a space: stays on the line of the previous word. */
static BOOL is_high_punctuation(uint16_t c) {
    return c == '!' || c == '?' || c == ';' || c == ':' || c == 0xbb /* » */;
}

static int copy_word(uint16_t *word, const uint16_t *text) {
    int length = 0;
    for (;;) {
        while (is_word_character(text[length])) {
            word[length] = text[length];
            ++length;
        }
        /* "mot !" and "« mot": the line cannot break at the space. */
        BOOL before_punctuation = text[length] == ' ' && is_high_punctuation(text[length + 1]);
        BOOL after_guillemet = text[length] == ' ' && length > 0 && word[length - 1] == 0xab /* « */
                               && is_word_character(text[length + 1]);
        if (length == 0 || !(before_punctuation || after_guillemet)) break;
        word[length] = ' ';
        ++length;
    }
    word[length] = 0;
    return length;
}

/* Letter spacing: the engine applies the spacing of ideographs from U+0080 on. The
 * threshold becomes U+0250, the same way in measuring and in drawing. */
static const BYTE measure_spacing_before[] = {0x81, 0xff, 0x80, 0x00, 0x00, 0x00,        /* cmp edi, 0x80 */
                                              0x73, 0x07, 0xf3, 0x0f, 0x10, 0x70, 0x64};
static const BYTE measure_spacing_after[] = {0x81, 0xff, 0x50, 0x02, 0x00, 0x00,         /* cmp edi, 0x250 */
                                             0x73, 0x07, 0xf3, 0x0f, 0x10, 0x70, 0x64};
static const BYTE render_spacing_before[] = {0x41, 0x81, 0xfd, 0x80, 0x00, 0x00, 0x00,   /* cmp r13d, 0x80 */
                                             0x73, 0x07, 0xf3, 0x0f, 0x10, 0x4f, 0x64};
static const BYTE render_spacing_after[] = {0x41, 0x81, 0xfd, 0x50, 0x02, 0x00, 0x00,    /* cmp r13d, 0x250 */
                                            0x73, 0x07, 0xf3, 0x0f, 0x10, 0x4f, 0x64};

/* Words of 5 letters or more: the engine subtracts from their measured width an
 * estimate based on the letter count, tuned for English. French words then look shorter
 * than they are and run off the right. The jump that skips this becomes unconditional. */
static const BYTE long_word_before[] = {0x85, 0xdb, 0x0f, 0x84, 0x82, 0x03, 0x00, 0x00,
                                        0x83, 0xbd, 0xc8, 0x1b, 0x00, 0x00, 0x00,
                                        0x0f, 0x84, 0x60, 0x03, 0x00, 0x00};  /* je (no subtraction) */
static const BYTE long_word_after[] = {0x85, 0xdb, 0x0f, 0x84, 0x82, 0x03, 0x00, 0x00,
                                       0x83, 0xbd, 0xc8, 0x1b, 0x00, 0x00, 0x00,
                                       0xe9, 0x61, 0x03, 0x00, 0x00, 0x90};   /* jmp, same target */

/* Labels of the settings sliders ("Lent ... Rapide"): the engine composes the image (two
 * labels of 122 px side by side) into a texture of 1132 px, the right label at x = 1010,
 * but draws only 1100 px of it: only 90 px of the right label showed. The two sliders using
 * it now draw the whole texture (mov edx, 1100 -> 1132 before the call that builds their
 * rectangles; the call, different for each, makes the pattern unique). */
static const BYTE slider_label1_before[] = {0xba, 0x4c, 0x04, 0x00, 0x00, 0x48, 0x8d, 0x4d, 0x68,
                                            0xe8, 0x2e, 0xb6, 0x03, 0x00};
static const BYTE slider_label1_after[] = {0xba, 0x6c, 0x04, 0x00, 0x00, 0x48, 0x8d, 0x4d, 0x68,
                                           0xe8, 0x2e, 0xb6, 0x03, 0x00};
static const BYTE slider_label2_before[] = {0xba, 0x4c, 0x04, 0x00, 0x00, 0x48, 0x8d, 0x4d, 0x68,
                                            0xe8, 0x21, 0x95, 0x03, 0x00};
static const BYTE slider_label2_after[] = {0xba, 0x6c, 0x04, 0x00, 0x00, 0x48, 0x8d, 0x4d, 0x68,
                                           0xe8, 0x21, 0x95, 0x03, 0x00};

typedef struct { const BYTE *before; const BYTE *after; size_t size; BYTE *address; } code_patch;
static code_patch code_patches[] = {
    {original_copy_word, NULL, sizeof(original_copy_word), NULL},  /* jumps to copy_word */
    {measure_spacing_before, measure_spacing_after, sizeof(measure_spacing_before), NULL},
    {render_spacing_before, render_spacing_after, sizeof(render_spacing_before), NULL},
    {long_word_before, long_word_after, sizeof(long_word_before), NULL},
    {slider_label1_before, slider_label1_after, sizeof(slider_label1_before), NULL},
    {slider_label2_before, slider_label2_after, sizeof(slider_label2_before), NULL},
};

static BYTE *find_unique(const BYTE *pattern, size_t size) {
    IMAGE_SECTION_HEADER *text = section(".text");
    if (!text || text->Misc.VirtualSize < size) return NULL;
    BYTE *start = game + text->VirtualAddress;
    BYTE *end = start + text->Misc.VirtualSize - size;
    BYTE *found = NULL;
    for (BYTE *p = start; p <= end; ++p) {
        if (*p == pattern[0] && memcmp(p, pattern, size) == 0) {
            if (found) return NULL;  /* ambiguous: unknown version */
            found = p;
        }
    }
    return found;
}

/* TRUE if the game code is decrypted and matches the supported version. */
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

/* ---------- Resource names redirection ---------- */

/* Resources shared by all languages, replaced by a name of the same length. */
static const char *const shared_names[][2] = {
    {"mode1.cbg", "modfr.cbg"},  /* language names in the settings: "Français" */
};

/* script_text_en.ctd -> script_text_fr.ctd, FONT_en_H00.mzp -> FONT_fr_H00.mzp,
 * Font010000.ccit -> Font040000.ccit... only if the archive holds the result. */
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
                /* suffix used to build some names (popup, teatime...) */
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

/* ---------- Engine data ---------- */

/* rdata_fr.bin: sequence of [u32 size][original bytes][replacement bytes] (positions of
 * the menu particles, line break rules...). Each original block must appear exactly once
 * in .rdata, otherwise it is skipped (other version of the game). */
static void apply_data_patches(void) {
    IMAGE_SECTION_HEADER *rdata = section(".rdata");
    if (!rdata || !data_patches) return;
    BYTE *start = game + rdata->VirtualAddress;
    const SIZE_T length = rdata->Misc.VirtualSize;
    DWORD position = 0;
    while (data_patches_size - position >= 4) {
        DWORD size;
        memcpy(&size, data_patches + position, 4);
        position += 4;
        if (size == 0 || size > (data_patches_size - position) / 2) return;
        const BYTE *before = data_patches + position, *after = before + size;
        position += 2 * size;
        BYTE *found = NULL;
        int matches = 0;
        for (BYTE *p = start; p + size <= start + length; ++p)
            if (*p == before[0] && memcmp(p, before, size) == 0 && ++matches == 1) found = p;
        if (matches == 1) write_memory(found, after, size);
    }
}

/* ---------- Activation ---------- */

static INIT_ONCE activation = INIT_ONCE_STATIC_INIT;
static BOOL french_active;

static void warn(const wchar_t *message) {
    MessageBoxW(NULL, message, L"Patch français Mahoyo", MB_OK | MB_ICONWARNING);
}

/* The game code is encrypted by Steam until the entry point: wait until it is readable.
 * `final` means that the game opens its archives, so the code should be readable; if the
 * expected code is still missing, the version is not supported. */
static BOOL CALLBACK activate(PINIT_ONCE once, PVOID final, PVOID *context) {
    (void)once; (void)context;
    if (!find_code_patches()) {
        if (!final) return FALSE;  /* try again on the next call */
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
    apply_data_patches();
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

/* ---------- Hooked functions ---------- */

static HANDLE (WINAPI *real_FindFirstFileW)(LPCWSTR, LPWIN32_FIND_DATAW);
static HANDLE (WINAPI *real_FindFirstFileExW)(LPCWSTR, FINDEX_INFO_LEVELS, LPVOID, FINDEX_SEARCH_OPS, LPVOID, DWORD);
static HANDLE (WINAPI *real_CreateFileW)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static BOOL (WINAPI *real_ReadFile)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
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

/* ---------- Files of the French archive first ----------
 * A resource of data00999.hfa named like a resource of another archive (e.g. img2168.mzp,
 * an image shared by all languages that the game looks for only in data02002.hfa) must
 * replace it. When the game reads the table of that other archive, the entry is moved
 * past the end of the file, to a virtual area whose reads are served by the DLL: from
 * data00999.hfa or, for a delta, from the file rebuilt in memory on first access (the
 * original of the game archive with its changed tiles replaced). Nothing changes on disk. */

#define MAX_ARCHIVES 256
#define MAX_REDIRECTS 4096
static struct open_archive {
    HANDLE handle;
    DWORD count;              /* 0 until the header is read */
    ULONGLONG virtual_start;  /* start of the virtual area: rounded file size */
    wchar_t path[MAX_PATH];   /* to read the originals of the deltas */
} open_archives[MAX_ARCHIVES];
static SRWLOCK open_archives_lock = SRWLOCK_INIT;

/* Entry redirected to the virtual area of a game archive. Tied to the file (its path), not
 * to the handle: the game may read the table with one handle and the entry with another. */
static struct redirect {
    ULONGLONG start;              /* position in the virtual area */
    DWORD size;                   /* size seen by the game */
    struct archive_entry *entry;
    ULONGLONG original_offset;    /* position of the original in the game archive (delta) */
    wchar_t path[MAX_PATH];       /* game archive */
} redirects[MAX_REDIRECTS];
static int redirect_count;

/* Files rebuilt from the deltas, kept in memory (once per entry). */
static BYTE *built_deltas[100000];

/* Tracks (or forgets) a file opened by the game. */
static void track_file(HANDLE handle, const wchar_t *path, BOOL is_other_archive) {
    if (handle == INVALID_HANDLE_VALUE) return;
    LARGE_INTEGER size = {0};
    if (is_other_archive && (!path || wcslen(path) >= MAX_PATH || !GetFileSizeEx(handle, &size)))
        is_other_archive = FALSE;
    AcquireSRWLockExclusive(&open_archives_lock);
    int free_slot = -1;
    for (int i = 0; i < MAX_ARCHIVES; ++i) {
        if (open_archives[i].handle == handle) open_archives[i].handle = NULL;  /* reused handle */
        if (!open_archives[i].handle && free_slot < 0) free_slot = i;
    }
    if (is_other_archive && free_slot >= 0) {
        struct open_archive *archive = &open_archives[free_slot];
        archive->handle = handle;
        archive->count = 0;
        archive->virtual_start = ((ULONGLONG)size.QuadPart + 0xFFFF) & ~0xFFFFULL;
        wcscpy_s(archive->path, MAX_PATH, path);
    }
    ReleaseSRWLockExclusive(&open_archives_lock);
}

/* Copy of the tracked archive; FALSE if the handle is not one. */
static BOOL find_open_archive(HANDLE handle, struct open_archive *result) {
    BOOL found = FALSE;
    AcquireSRWLockShared(&open_archives_lock);
    for (int i = 0; i < MAX_ARCHIVES && !found; ++i) {
        if (open_archives[i].handle == handle) {
            *result = open_archives[i];
            found = TRUE;
        }
    }
    ReleaseSRWLockShared(&open_archives_lock);
    return found;
}

/* Places an entry in the virtual area of its archive (at the same place when the table is
 * read again, by any handle). */
static struct redirect *place(struct open_archive *archive, struct archive_entry *entry, DWORD size,
                              ULONGLONG original_offset) {
    ULONGLONG end = archive->virtual_start;
    for (int i = 0; i < redirect_count; ++i) {
        if (_wcsicmp(redirects[i].path, archive->path) != 0) continue;
        if (redirects[i].entry == entry) return &redirects[i];
        end = max(end, (redirects[i].start + redirects[i].size + 0xF) & ~0xFULL);
    }
    if (redirect_count == MAX_REDIRECTS) return NULL;
    struct redirect *redirect = &redirects[redirect_count++];
    redirect->start = end;
    redirect->size = size;
    redirect->entry = entry;
    redirect->original_offset = original_offset;
    wcscpy_s(redirect->path, MAX_PATH, archive->path);
    return redirect;
}

static void redirect_replaced_entries(HANDLE handle, ULONGLONG position, BYTE *buffer, DWORD size) {
    AcquireSRWLockExclusive(&open_archives_lock);
    for (int i = 0; i < MAX_ARCHIVES; ++i) {
        struct open_archive *archive = &open_archives[i];
        if (archive->handle != handle) continue;
        if (position == 0 && size >= 16) {
            DWORD count = 0;
            if (memcmp(buffer, "HUNEXGGEFA10", 12) == 0) memcpy(&count, buffer + 12, 4);
            archive->count = count;
        }
        const ULONGLONG data_start = 16 + (ULONGLONG)archive->count * HFA_ENTRY_SIZE;
        const ULONGLONG first = position <= 16 ? 0 : (position - 16 + HFA_ENTRY_SIZE - 1) / HFA_ENTRY_SIZE;
        for (ULONGLONG index = first; index < archive->count; ++index) {
            const ULONGLONG entry = 16 + index * HFA_ENTRY_SIZE;
            if (entry + HFA_NAME_SIZE + 8 > position + size) break;
            BYTE *name = buffer + (entry - position);
            if (!memchr(name, 0, HFA_NAME_SIZE)) continue;
            struct archive_entry *replacement = (struct archive_entry *)find_entry((const char *)name);
            if (!replacement) continue;
            DWORD fields[2];
            memcpy(fields, name + HFA_NAME_SIZE, sizeof(fields));
            /* a delta applies only to the expected original; otherwise the original is kept */
            if (replacement->delta && fields[1] != replacement->original_size) continue;
            struct redirect *redirect = place(archive, replacement,
                                              replacement->delta ? replacement->result_size : replacement->size,
                                              data_start + fields[0]);
            if (!redirect || redirect->start - data_start > 0xFFFFFFFFULL) continue;
            fields[0] = (DWORD)(redirect->start - data_start);
            fields[1] = redirect->size;
            memcpy(name + HFA_NAME_SIZE, fields, sizeof(fields));
        }
        break;
    }
    ReleaseSRWLockExclusive(&open_archives_lock);
}

static BOOL read_archive(DWORD offset, void *buffer, DWORD size) {
    LARGE_INTEGER source;
    source.QuadPart = (LONGLONG)archive_data_start + offset;
    AcquireSRWLockExclusive(&archive_file_lock);
    BOOL result = SetFilePointerEx(archive_file, source, NULL, FILE_BEGIN) && read_exact(archive_file, buffer, size);
    ReleaseSRWLockExclusive(&archive_file_lock);
    return result;
}

static DWORD read_u16(const BYTE *p) { WORD value; memcpy(&value, p, 2); return value; }
static DWORD read_u32(const BYTE *p) { DWORD value; memcpy(&value, p, 4); return value; }

/* Whole file of a delta: the entries of the original (mrgd00 archive: table of [sector,
 * offset, sector count, size & 0xFFFF], sectors of 0x800 bytes), with the changed ones
 * replaced, written again like utils/steam/mzp.py (_write_entries). */
static BYTE *build_delta(const struct redirect *redirect) {
    const struct archive_entry *entry = redirect->entry;
    BYTE *original = HeapAlloc(GetProcessHeap(), 0, entry->original_size);
    BYTE *delta = HeapAlloc(GetProcessHeap(), 0, entry->size);
    BYTE *result = HeapAlloc(GetProcessHeap(), 0, entry->result_size);
    HANDLE file = INVALID_HANDLE_VALUE;
    BOOL success = FALSE;
    if (!original || !delta || !result || !read_archive(entry->offset, delta, entry->size)) goto done;
    file = real_CreateFileW(redirect->path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, NULL, OPEN_EXISTING, 0, NULL);
    LARGE_INTEGER position;
    position.QuadPart = (LONGLONG)redirect->original_offset;
    if (file == INVALID_HANDLE_VALUE || !SetFilePointerEx(file, position, NULL, FILE_BEGIN) ||
        !read_exact(file, original, entry->original_size)) goto done;
    if (entry->original_size < 8 || memcmp(original, "mrgd00", 6) != 0) goto done;
    const DWORD count = read_u16(original + 6);
    const DWORD changed = read_u16(delta + 16);
    const DWORD table_end = 8 + count * 8;
    if (table_end > entry->original_size || table_end > entry->result_size ||
        DELTA_HEADER_SIZE + changed * 6 > entry->size) goto done;
    memcpy(result, original, 8);
    DWORD written = 0;  /* bytes written after the table */
    for (DWORD i = 0; i < count; ++i) {
        const BYTE *item = original + 8 + i * 8;
        /* entry of the original: its size is found from its sector count */
        const DWORD start = read_u16(item) * 0x800u + read_u16(item + 2);
        const DWORD sectors = read_u16(item + 4);
        DWORD length = read_u16(item + 6);
        while ((start + length + 0x7FFu) / 0x800u - start / 0x800u < sectors) length += 0x800u;
        const BYTE *data = original + table_end + start;
        BOOL replaced = FALSE;
        DWORD offset = DELTA_HEADER_SIZE + changed * 6;
        for (DWORD k = 0; k < changed; ++k) {
            const BYTE *change = delta + DELTA_HEADER_SIZE + k * 6;
            if (read_u16(change) == i) {
                data = delta + offset;
                length = read_u32(change + 2);
                replaced = TRUE;
                break;
            }
            offset += read_u32(change + 2);
        }
        if (replaced ? offset + length > entry->size : table_end + start + length > entry->original_size) goto done;
        const DWORD padding = 8 - length % 8;
        if (table_end + written + length + padding > entry->result_size) goto done;
        const WORD fields[4] = {(WORD)(written / 0x800u), (WORD)(written % 0x800u),
                                (WORD)((written + length + 0x7FFu) / 0x800u - written / 0x800u), (WORD)length};
        memcpy(result + 8 + i * 8, fields, sizeof(fields));
        memcpy(result + table_end + written, data, length);
        memset(result + table_end + written + length, 0xFF, padding);
        written += length + padding;
    }
    success = table_end + written == entry->result_size;
done:
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    if (original) HeapFree(GetProcessHeap(), 0, original);
    if (delta) HeapFree(GetProcessHeap(), 0, delta);
    if (!success && result) {
        HeapFree(GetProcessHeap(), 0, result);
        result = NULL;
    }
    return result;
}

/* Read in the virtual area: the redirected entry holding the position. */
static BOOL read_virtual(const struct open_archive *archive, HANDLE handle, ULONGLONG position, LPVOID buffer,
                         DWORD size, LPDWORD read, LPOVERLAPPED overlapped) {
    BOOL result = FALSE;
    DWORD done = 0;
    AcquireSRWLockExclusive(&open_archives_lock);
    for (int i = 0; i < redirect_count; ++i) {
        const struct redirect *redirect = &redirects[i];
        if (position < redirect->start || position >= redirect->start + redirect->size ||
            _wcsicmp(redirect->path, archive->path) != 0) continue;
        const DWORD offset = (DWORD)(position - redirect->start);
        done = min(size, redirect->size - offset);
        if (!redirect->entry->delta) {
            result = read_archive(redirect->entry->offset + offset, buffer, done);
        } else {
            BYTE **built = &built_deltas[redirect->entry - archive_entries];
            if (!*built) *built = build_delta(redirect);
            if (*built) {
                memcpy(buffer, *built + offset, done);
                result = TRUE;
            }
        }
        break;
    }
    ReleaseSRWLockExclusive(&open_archives_lock);
    if (!result) return FALSE;
    if (read) *read = done;
    if (overlapped) {
        overlapped->Internal = 0;
        overlapped->InternalHigh = done;
        if (overlapped->hEvent) SetEvent(overlapped->hEvent);
    } else {
        LARGE_INTEGER next;
        next.QuadPart = (LONGLONG)(position + done);
        SetFilePointerEx(handle, next, NULL, FILE_BEGIN);
    }
    return TRUE;
}

static HANDLE WINAPI hook_CreateFileW(LPCWSTR path, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES security,
                                      DWORD disposition, DWORD flags, HANDLE template_file) {
    BOOL archive = is_archive_path(path);
    if (archive) try_activate(TRUE);
    HANDLE handle = real_CreateFileW(path, access, share, security, disposition, flags, template_file);
    const wchar_t *file_name = path ? wcsrchr(path, L'\\') : NULL;
    file_name = file_name ? file_name + 1 : path;
    track_file(handle, path, archive && french_active && _wcsicmp(file_name, ARCHIVE_NAME) != 0);
    return handle;
}

static BOOL WINAPI hook_ReadFile(HANDLE handle, LPVOID buffer, DWORD size, LPDWORD read, LPOVERLAPPED overlapped) {
    struct open_archive archive;
    if (!french_active || !find_open_archive(handle, &archive))
        return real_ReadFile(handle, buffer, size, read, overlapped);
    LARGE_INTEGER position = {0};
    if (overlapped) {
        position.LowPart = overlapped->Offset;
        position.HighPart = (LONG)overlapped->OffsetHigh;
    } else {
        LARGE_INTEGER zero = {0};
        if (!SetFilePointerEx(handle, zero, &position, FILE_CURRENT))
            return real_ReadFile(handle, buffer, size, read, overlapped);
    }
    if ((ULONGLONG)position.QuadPart >= archive.virtual_start)
        return read_virtual(&archive, handle, (ULONGLONG)position.QuadPart, buffer, size, read, overlapped);
    BOOL result = real_ReadFile(handle, buffer, size, read, overlapped);
    DWORD done = 0;
    if (result && (read ? (done = *read) : (overlapped && GetOverlappedResult(handle, overlapped, &done, FALSE))))
        redirect_replaced_entries(handle, (ULONGLONG)position.QuadPart, buffer, done);
    return result;
}

/* TEXT/5 resource: system texts (CSV ja,en,zc,zt; French takes the en column). */
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

/* Window title: "WITCH ON THE HOLY NIGHT ( ver 1.1 ) - Patch FR". */
#define WINDOW_TITLE L"WITCH ON THE HOLY NIGHT"
#define TITLE_SUFFIX L" - Patch FR"

static HWND (WINAPI *real_CreateWindowExW)(DWORD, LPCWSTR, LPCWSTR, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, LPVOID);
static BOOL (WINAPI *real_SetWindowTextW)(HWND, LPCWSTR);
static HWND (WINAPI *real_FindWindowW)(LPCWSTR, LPCWSTR);

/* `title` with the suffix in `buffer`, or `title` unchanged. */
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
    {"kernel32.dll", "ReadFile", (void **)&real_ReadFile, (void *)hook_ReadFile},
    {"kernel32.dll", "FindResourceW", (void **)&real_FindResourceW, (void *)hook_FindResourceW},
    {"kernel32.dll", "LoadResource", (void **)&real_LoadResource, (void *)hook_LoadResource},
    {"kernel32.dll", "SizeofResource", (void **)&real_SizeofResource, (void *)hook_SizeofResource},
    {"kernel32.dll", "LockResource", (void **)&real_LockResource, (void *)hook_LockResource},
    {"user32.dll", "CreateWindowExW", (void **)&real_CreateWindowExW, (void *)hook_CreateWindowExW},
    {"user32.dll", "SetWindowTextW", (void **)&real_SetWindowTextW, (void *)hook_SetWindowTextW},
    {"user32.dll", "FindWindowW", (void **)&real_FindWindowW, (void *)hook_FindWindowW},
};

/* Replaces entries of the import table of WoH.exe (not of the other modules). */
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

/**
 * decode.c - Parsing stringhe formato "comando valore; comando2 valore2;"
 *
 * Uso:
 *   char valore[64];
 *   decode("x", "x 123; y 456; lux 0.50;", valore, sizeof(valore));
 *   // valore = "123"
 */

#include <string.h>
#include <stdio.h>

/**
 * Estrae il valore associato a un comando da una stringa.
 *
 * @param comando   Nome del parametro da cercare (es. "x", "lux", "roll")
 * @param stringa   Stringa di input formato "cmd val; cmd2 val2; ..."
 * @param out       Buffer per il valore estratto
 * @param out_size  Dimensione del buffer out
 * @return          1 se trovato, 0 se non trovato
 */
int decode(const char *comando, const char *stringa, char *out, size_t out_size)
{
    const char *p;
    const char *val_start;
    const char *val_end;
    size_t cmd_len = strlen(comando);
    size_t val_len;

    /* Cerca comando nella stringa */
    p = stringa;
    while ((p = strstr(p, comando)) != NULL) {
        /* Verifica che sia inizio stringa o preceduto da spazio/; */
        if (p != stringa && *(p - 1) != ' ' && *(p - 1) != ';') {
            p++;
            continue;
        }

        /* Verifica che dopo il comando ci sia uno spazio */
        if (*(p + cmd_len) != ' ') {
            p++;
            continue;
        }

        /* Trovato! Estrai valore */
        val_start = p + cmd_len + 1;  /* Salta "comando " */

        /* Trova fine valore (;) o fine stringa */
        val_end = strchr(val_start, ';');
        if (val_end == NULL) {
            val_end = val_start + strlen(val_start);
        }

        /* Copia valore in out */
        val_len = val_end - val_start;
        if (val_len >= out_size) {
            val_len = out_size - 1;
        }
        strncpy(out, val_start, val_len);
        out[val_len] = '\0';

        return 1;  /* Trovato */
    }

    out[0] = '\0';
    return 0;  /* Non trovato */
}


/* --- Test --- */
#ifdef TEST_DECODE
int main(void)
{
    char valore[64];
    const char *test = "x 123; y 456; lux 0.50; roll 1.20; yaw 0.30; pitch 0.10; left 0; right 1;";

    printf("Stringa: %s\n\n", test);

    if (decode("x", test, valore, sizeof(valore)))
        printf("x = %s\n", valore);

    if (decode("y", test, valore, sizeof(valore)))
        printf("y = %s\n", valore);

    if (decode("lux", test, valore, sizeof(valore)))
        printf("lux = %s\n", valore);

    if (decode("roll", test, valore, sizeof(valore)))
        printf("roll = %s\n", valore);

    if (decode("left", test, valore, sizeof(valore)))
        printf("left = %s\n", valore);  

    if (decode("nonexist", test, valore, sizeof(valore)))
        printf("nonexist = %s\n", valore);
    else
        printf("nonexist: non trovato\n");

    return 0;
}
#endif

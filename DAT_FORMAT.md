# Dokumentacja struktury plików zapisu .DAT Clash

## 1. Ogólna struktura pliku

Typowy plik ma stały rozmiar **586 414 bajtów**. Siatka mapy jest zawsze **100 x 100** (stała silnika – brak pola z wymiarami w pliku).

| Offset (hex) | Offset (dec) | Sekcja | Rozmiar |
|---|---|---|---|
| 0x000000 | 0 | Nazwa zapisu gry | 16 B |
| 0x000001 | 16 | Siatka kafelków | (10 000 x 14 B) = 140 000 B |
| 0x0222F0 | 140 016 | Bloki graczy + mgła wojny (5 graczy) | ~7 115 B |
| 0x023EF0 | 146 672 | Sloty oddziałów | (rekordy po 725 B) = ~363 tys. B |
| 0x07C6FA | 509 690 | Tabela budynków | (rekordy po 467 B) |
| 0x087D66 | 556 390 | Siatka zajętości kafelków | (100 x 100 x 2 B) = 20 000 B |

---

### Nazwa zapisu gry
16 bajtów. Tekst wpisywany przez gracza przy zapisywaniu gry.

---

## 2. Siatka kafelków (offset 16)

10 000 rekordów po **14 bajtów**, w porządku **kolumnowym** ("idx = x * 100 + y").  
Adres rekordu kafelka: `offset = 16 + (x * 100 + y) * 14`.

Każdy rekord to 7 pól **u16** little-endian:

| Pole | Bajty | Znaczenie | Uwagi |
|---|---|---|---|
| 'tex_id' | 0-1 | Bazowa tekstura kafelka | |
| 'overlay1' | 2-3 | Nakładka | '0xFFFF' = brak; |
| 'road' | 4-5 | Droga / obiekt | '0xFFFF' = brak; np. droga '0x0363' = 866 |
| 'flags' | 6-7 | | |
| - | 8-9 | 0 lub 5 ? | |
| - | 10-11 | zwykle 0 | |
| - | 12-13 | zwykle 0 | |

Koniec siatki na offsetie **140 016**

---

## 3. Bloki graczy i mgła wojny (offset 140 016)

Za siatką kafelków znajduje się sekcja 5 graczy. Każdy gracz ma **blok o stałym kroku 1423 bajtów**.

- **Nazwa gracza** - ASCII zakończone `0x00`, pole pod adresem `140044 + owner * 1423` (

### 3.1. Bitmapa mgły wojny

Każdy gracz ma własną bitmapę widoczności (1 bit = 1 kafelek). Ustawiony bit = kafelek **odkryty**.

- Baza gracza: `fog_base(owner) = 140084 + owner * 1423`
- **Układ kolumnowy**: kolumna `x` (0-99) zajmuje 13 bajtów; w bajcie `k` bit `b` koduje wiersz `y = k*8 + b` (bit 0 / LSB = najmniejszy `y`).


- Mgła jest **kumulatywna** - ruch jednostki odsłania nowe pola, ale nigdy nie zasłania już odkrytych.
- W pełni odkryta mapa = 9902 ustawionych bitów;
- **Zasięg widzenia** = Tymczasowo ustawione na szytwno 6 kafelków (pojedynczy krok jednostki odsłania 1uk na dystansie euklidesowym do ~6,4).


```
offset = fog_base + x * 13 + (y >> 3)
bit = 1 << (y & 7)
```

---

## 4. Sloty oddziałów (offset `0x023EF0`)

Oddziały leżą na **stałej siatce** slotów co 725 bajtów (**0x2D5**), zakotwiczonej pod `SQUAD_ANCHOR = 0x023EF0`.  
Adres slotu numer `k`: `b = 0x023EF0 + k * 725`.

Silnik **skanuje** sloty po zawartości – **brak licznika oddziałów** – sloty mogą być rzadkie (z lukami).

### 4.1. Nagłówki slotu

| Offset w slocie | Znaczenie | Uwagi |
|---|---|---|
| b+2 ... b+5 | Wskaźnik render/instancji | runtime, odbudowywany przy wczytaniu |
| b+6, b+7 | X (kolumna), u16 | współrzędna kafelka |
| b+8, b+9 | Y (wiersz), u16 | współrzędna kafelka |
| b+10 | Właściciel (gracz) | 0=czerwony, 1=niebieski, 2=żółty, 3=biały, 4=zielony |
| b+11 | 0 dla wszystkich | |
| b+12 | Lista członków (rekordy po 31 B) | zob. 4.2 |

- Slot jest **aktywnym oddziałem**, gdy: typ dowódcy `d[b+12]` ∈ 0..34 oraz `d[b+13]` == 0 (górny bajt `u16`), `d[b+10]` ≤ 4, `d[b+14]` = owner (kopia właściciela).
- **Pusty slot**: `u16` w b+12 == 0xFFFF (lub zera) → 0 członków → nieaktywny.

### 4.2. Rekord jednostki/członka oddziału (31 bajtów)

Adres członka oddziału `j`: `0 = b + 12 + 31 * j` (do 10 członków; `0xFFFF` kończy listę).

| Offset w rekordzie | Nazwa | Znaczenie |
|---|---|---|
| 0+0, 0+1 | M_TYPE | Typ jednostki (`u16`; górny bajt 0) |
| 0+2 | M_OWNER | Właściciel (= właściciel oddziału) |
| 0+3 ... 0+7 | Stan instancji/renderu (m.in. kierunek na `0+3`) | |
| 0+8 | M_MOVE | Punkty akcji / ruchu (PA) |
| 0+9 | M_HP | Aktualne HP (maks. 100) |
| 0+10 | M_FATIGUE | Zmęczenie |
| 0+11 | M_MORALE | Morale (bazowo 10 lub 6) |
| 0+12 | M_ADV | Zaawansowanie (młodszy półbajt `0x0F`; zachować starszy przy zapisie) |
| 0+13 |  | |

- **Atak / pancerz / dystans / zdolności NIE są zapisywane per jednostka** – silnik wyprowadza je z typu i poziomu zaawansowania.

---

## 5. Siatka zajętości kafelków – widoczność jednostek (offset `0x807D66`)

To **kluczowa struktura decydująca o rysowaniu jednostek**. Bez wpisu tutaj świeżo dodany oddział jest _zaznaczalny_, ale **niewidoczny** aż do pierwszego ruchu (silnik renderuje jednostki właśnie z tej tablicy).

- Baza: `UNIT_INDEX_BASE = 556390` (`0x807D66`)
- **Układ kolumnowy**: kolumna `x` = 100 wierszy x 2 bajty = 200 B.
- Adres komórki kafelka `(x, y)`:

```
offset = 556390 + x * 200 + y * 2
```

- Komórka `(u16)` = **indeks slotu** oddziału stojącego na kafelku: `k = (adres_slotu - 0x023EF0) / 725`, albo `0xFFFF` gdy pole puste.
- Budynki/zamki mają w swoich komórkach ustawiony bit `0x8000`.
- Tablica obejmuje `556390 + 576390` (100 x 100 x 2 = 20 000 B).

---

## 6. Tabela budynków – zamki, twierdze, wieże (offset `0x7C6FA`)

Budynki **nie** są zapisane w siatce kafelków. Łączą w osobnej **tabeli o stałych rekordach 467 bajtów**, od `BUILDING_TABLE_BASE = 0x7C6FA` (509 690).

### 6.1. Nagłówek rekordu budynku

| Offset | Znaczenie |
|---|---|
| 0+0 | X (lewy-górny kafelek, 1-99) |
| 0+1 | Y |
| 0+2 | **Właściciel** (0-4) – wyznacza kolor renderowania |
| 0+3 |   |
| 0+4 | **Typ** (0/1/2; **0xFF** = pusty slot + point) |
| 0+5 | Opcjonalna nazwa ASCII zakończona `0x00`, dalej garnizon (jednostki, krok 31 B) |

### 6.2. Typ, rozmiar i tekstury

Kolor budynku wyznacza **Właściciel** (0+2), a rodzaj – **typ** (0+4):

| Typ | Rodzaj | Rozmiar | Bazowe ID tekstury | Krok na gracza |
|---|---|---|---|---|
| 0 | Wieża | 1x1 | `12 + owner` (niebieski = 13) | 1 |
| 1 | Twierdza | 2x2 | `93 + 4*owner` (niebieski = 97-100) | 4 |
| 2 | Zamek | 2x2 | `237 + 40*owner` (czerwony = 237, niebieski = 277) | 40 |

- ID kafelka w bloku 2x2: `id = base + dx + 2*dy` (dla dx, dy ∈ {0,1}); wieża = pojedyncze `base`.
- Tekstury: `res/minimum/BUILDIN[N].S32/...{id}.png` (64x64), gdzie `N` = cyfra z nazwy aktywnej palety.


---

## 7. Tekstury i sprite'y

### 7.1. Kafelki mapy
- `res/normal/BACKGR[1,2,3].S32/...{id}.png` – paleta zależna od aktywnego zestawu.

### 7.2. Jednostki
- `res/normal/<PREFIX><COLOR>.S32/<PREFIX><COLOR>.S32_<ID>.png`
- `COLOR` = `owner + 1` (1=czerwony, 2=niebieski, 3=żółty, 4=biały, 5=zielony).
- 64 klatki = 8 kierunków x 8 klatek animacji; reprezentatywna klatka kierunku `d` to `d*8`.

### 7.3. Tabela typów jednostek (`type_id` = indeks z clash.yo.pl/adresy-jednostek)

 ID | Prefix | Nazwa |
|---:|--------|-------|
| 0  | PEON  | Pospolite ruszenie |
| 1  | INFL  | Lekka piechota  |   
| 2  | INFH  | Ciężka piechota  |  
| 3  | SPRL  | Pikinier |          
| 4  | SPRH  | Halabardnik |       
| 5  | CAVL  | Lekka jazda |       
| 6  | CAVH  | Ciężka jazda |      
| 7  | RYC   | Rycerstwo |         
| 8  | DRAG  | Dragon |            
| 9  | ARCH  | Łucznik |           
| 10 | KUSZA | Kusznik  |          
| 11 | MUSZK | Muszkieter  |       
| 12 | KATAP | Katapulta |         
| 13 | TARAN | Taran |             
| 14 | ARMAT | Armata |            
| 15 | LESN  | Leśnik |            
| 16 | GORAL | Góral |              
| 17 | BUDON | Budowniczy |         
| 18 | WORM  | Czerw |
| 19 | SLON  | Słoń |
| 20 | CYKL  | Cyklop |
| 21 | TROL  | Troll |
| 22 | SCORP | Skorpion |
| 23 | SZK   | Szkielet |
| 24 | MAG   | Mag |
| 25 | DUCH  | Duch |
| 26 | ORZEL | Orzeł |
| 27 | PEGAZ | Pegaz |
| 28 | SKRZ  | Skrzydlak |
| 29 | WAZKA | Ważka |
| 30 | SMOK  | Smok |
| 31 | GOLD  | Złoto |
| 32 | PEAS  | Chłopi |
| 33 | SPEC  | Dowódca (syn) |
| 34 | SPECK | Dowódca (córka) |
|    |       | |

"""AC Travanca - motor de jogo (liga offline + simulação online detalhada)."""
import random, math, statistics

KEYS = ("def", "dri", "rem", "fis", "pas", "vel")

# ---------- Classes ----------
class Jogador:
    def __init__(s, nome, pos, a): s.nome, s.pos, s.a = nome, pos, a
class JogadorDeLinha(Jogador): pass
class GuardaRedes(Jogador): pass

# ---------- Pesos por posição (Drible+Remate+Velocidade = 5% no total -> 5/3 cada) ----------
_t = lambda d, e=0: {**{k: 0 for k in KEYS}, **d}
W = {
 "D":  {"def": .42, "fis": .42, "pas": .11, "dri": .05/3, "rem": .05/3, "vel": .05/3},
 "DC": {"def": .43, "fis": .43, "pas": .10, "dri": .04/3, "rem": .04/3, "vel": .04/3},
 "DL": {"def": .31, "fis": .31, "pas": .15, "vel": .10, "dri": .10, "rem": .03},
 "MC": {"def": .10, "dri": .30, "fis": .10, "pas": .35, "vel": .05, "rem": .10},
 "ML": {"dri": .30, "rem": .15, "pas": .25, "vel": .20, "def": .05, "fis": .05},
 "M3": {"def": .10, "dri": .30, "fis": .10, "pas": .35, "vel": .10, "rem": .05},
 "A":  {"dri": .23, "rem": .28, "fis": .23, "pas": .10, "vel": .15, "def": .01},
}
# Ordem = nº das imagens 1..7
FORM = {
 1: ["GR", "D", "D", "MC", "ML", "ML", "A"],
 2: ["GR", "DL", "DL", "DC", "MC", "A", "A"],
 3: ["GR", "D", "M3", "D", "M3", "A", "A"],
}
# Posição (x 0=própria baliza..1=baliza adversária, y 0..1) lida das imagens
COORD = {
 1: [(.09,.49),(.25,.67),(.25,.39),(.47,.50),(.47,.19),(.48,.83),(.69,.53)],
 2: [(.09,.49),(.33,.80),(.32,.22),(.27,.51),(.45,.50),(.62,.66),(.61,.34)],
 3: [(.09,.49),(.25,.65),(.42,.28),(.24,.40),(.42,.71),(.62,.64),(.61,.35)],
}
def grupo(r): return {"G": "Guarda-redes", "D": "Defesa", "M": "Médio", "A": "Avançado"}[r[0]]

def escalar(j, r):
    """Aplica as regras de posição: -5 fora da posição; GR fora de posto = 40 a tudo; não-GR a GR = 40."""
    g = grupo(r)
    gk = "Guarda-redes" in j.pos
    if g == "Guarda-redes":
        return GuardaRedes(j.nome, j.pos, {"gr": j.a["gr"] if gk else 40})
    if gk:
        return JogadorDeLinha(j.nome, j.pos, {k: 40 for k in KEYS})
    pen = 0 if g in j.pos else 5
    return JogadorDeLinha(j.nome, j.pos, {k: max(0, v - pen) for k, v in j.a.items()})

def forca_jogador(p, r):
    return p.a["gr"] if r == "GR" else sum(W[r][k] * p.a[k] for k in KEYS)

def montar(plantel, tatica):
    """plantel: 7 Jogador por ordem dos slots -> lista de efetivos."""
    return [escalar(j, r) for j, r in zip(plantel, FORM[tatica])]

def forca_equipa(efetivos, tatica):
    return statistics.mean(forca_jogador(p, r) for p, r in zip(efetivos, FORM[tatica]))

# ---------- Liga offline (rápida, só força média) ----------
# Afinação: a FORÇA domina o resultado (K_FORCA), o acaso é baixo (ruídos gaussianos pequenos).
RUIDO_FORCA, RUIDO_GOLOS, K_FORCA, BASE_GOLOS = 1.5, .8, .15, 1.6

def _golos(fa, fb):
    # dif de força (com ruído gauss baixo) -> golos esperados = BASE + K*dif ; golos reais = gauss(esperado, 0.8) arredondado
    d = (fa + random.gauss(0, RUIDO_FORCA)) - (fb + random.gauss(0, RUIDO_FORCA))
    g = lambda x: max(0, round(random.gauss(max(.2, BASE_GOLOS + K_FORCA * x), RUIDO_GOLOS)))
    return g(d), g(-d)

def _calendario(n):
    """Método do círculo: n-1 jornadas na 1ª volta e as mesmas na 2ª com casa/fora trocados (2 jogos contra cada equipa)."""
    t, R = list(range(n)), []
    for _ in range(n - 1):
        R.append([(t[i], t[n - 1 - i]) for i in range(n // 2)]); t = [t[0]] + [t[-1]] + t[1:-1]
    return R + [[(b, a) for a, b in r] for r in R]

def _reg(T, n, m, s):
    t = T[n]; t["j"] += 1; t["gm"] += m; t["gs"] += s
    if m > s: t["v"] += 1; t["pts"] += 3
    elif m == s: t["e"] += 1; t["pts"] += 1
    else: t["d"] += 1

def simular_liga_offline(efetivos, tatica, adversarios, nome="AC Travanca"):
    """Devolve (tabela, marcadores, jogos do utilizador por jornada com os respetivos marcadores)."""
    nomes = [nome] + [a for a, _ in adversarios]; forca = [forca_equipa(efetivos, tatica)] + [f for _, f in adversarios]
    T = {n: dict(equipa=n, pts=0, j=0, v=0, e=0, d=0, gm=0, gs=0) for n in nomes}
    pesos = [{"G": 0, "D": .6, "M": 2, "A": 4}[r[0]] * p.a.get("rem", 0) for p, r in zip(efetivos, FORM[tatica])]
    marc, jogos = {p.nome: 0 for p in efetivos}, []
    for r, rodada in enumerate(_calendario(len(nomes)), 1):
        for i, j in rodada:
            a, b = _golos(forca[i], forca[j]); _reg(T, nomes[i], a, b); _reg(T, nomes[j], b, a)
            if 0 in (i, j):
                gm, gs = (a, b) if i == 0 else (b, a)
                quem = [random.choices(efetivos, pesos)[0].nome for _ in range(gm)]
                for q in quem: marc[q] += 1
                jogos.append(dict(rodada=r, adv=nomes[j if i == 0 else i], casa=i == 0, gm=gm, gs=gs, res="V" if gm > gs else "E" if gm == gs else "D",
                                  marc=[dict(n=q, m=m) for q, m in zip(quem, sorted(random.sample(range(1, 61), min(gm, 60))))]))
    tab = sorted(T.values(), key=lambda t: (-t["pts"], -(t["gm"] - t["gs"]), -t["gm"]))
    for t in tab: t["gd"] = t["gm"] - t["gs"]
    return tab, sorted(marc.items(), key=lambda x: -x[1]), jogos

# ---------- Motor online detalhado (implementado em online_match_engine.py) ----------

def _gerar_tabela_consola(nA, nB, st):
    L = [f"=== RESULTADO FINAL: {nA} {st[0]['golos']} - {st[1]['golos']} {nB} ===",
         f"{'':24}{nA[:14]:>14}{nB[:14]:>14}", "-" * 52]
    for lab, k in (("Golos", "golos"), ("Posse (%)", "posse_pct"), ("Remates", "rem"), ("À baliza", "bal"), ("Defesas do GR", "def_"), ("Desarmes", "des"), ("Interceções", "inte")):
        L.append(f"{lab:24}{st[0][k]:>14}{st[1][k]:>14}")
    L.append(f"{'Passes (compl./tent.)':24}{str(st[0]['pc'])+'/'+str(st[0]['pt']):>14}{str(st[1]['pc'])+'/'+str(st[1]['pt']):>14}")
    if "mvp" in st[0]:
        m = st[0]["mvp"]
        L.append(f"\nHomem do Jogo (MVP): {m['nome']} ({m['equipa']}) - Nota {m['nota']} [{m['resumo']}]")
    return "\n".join(L)

def match_engine_online(nA, nB, plA, plB, tA, tB, fnA=None, fnB=None):
    """Executa apenas o modo online no motor espacial independente (com suporte para funções por jogador)."""
    from online_match_engine import FootballManagerEngine, POSITION_LAYOUT
    return FootballManagerEngine(nA, nB, plA, plB, tA, tB, COORD, POSITION_LAYOUT, fnA, fnB).jogar()

if __name__ == "__main__":   # demo narrada na consola
    mk = lambda n: [Jogador(f"{n}{i}", ["Guarda-redes"] if i == 0 else ["Defesa", "Médio", "Avançado"],
                    {"gr": random.randint(70, 90)} if i == 0 else {k: random.randint(60, 90) for k in KEYS}) for i in range(7)]
    ev, st = match_engine_online("Azuis", "Amarelos", mk("A"), mk("B"), 1, 3)
    for e in ev: print(f"{e['m']:02d}' {e['txt']}")
    print(_gerar_tabela_consola("Azuis", "Amarelos", st))

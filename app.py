"""AC Travanca - servidor Flask + Flask-SocketIO.
Local:   python app.py      Produção: gunicorn -k gthread --threads 100 -w 1 app:app
async_mode='threading' (+simple-websocket) evita eventlet/gevent, que partem em Python recente."""
import os, uuid, random, sqlite3, glob, threading, unicodedata
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file
from flask_socketio import SocketIO, join_room, leave_room, emit
import match_engine as me
import online_match_engine as online_me

BASE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FOLDER = "templates" if os.path.isfile(os.path.join(BASE, "templates", "index.html")) else "."
app = Flask(__name__, template_folder=TEMPLATE_FOLDER)
socketio = SocketIO(
    app,
    async_mode="threading",
    cors_allowed_origins="*",
    ping_interval=25,
    ping_timeout=60,
)
DB = os.environ.get("DB_PATH", os.path.join(BASE, "ranking.db"))
OFF, SALAS = {}, {}
SALAS_LOCK = threading.RLock()

# ---------- Excel (pandas) ----------
def _norm(s):
    """Normaliza texto removendo acentos, espaços e underscores para comparação robusta em Linux/Render."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    return s.casefold().replace(" ", "").replace("_", "").replace("-", "")

def _xlsx(prefixo):
    alvo = _norm(prefixo)
    for pasta in (BASE, os.path.join(BASE, "dados")):
        if not os.path.isdir(pasta):
            continue
        for f in glob.glob(os.path.join(pasta, prefixo + "*.xlsx")):
            return f
        for nome_fich in os.listdir(pasta):
            if nome_fich.lower().endswith(".xlsx") and _norm(nome_fich).startswith(alvo):
                return os.path.join(pasta, nome_fich)
    raise FileNotFoundError(f"Excel '{prefixo}*.xlsx' não encontrado")

def _xlsx_online():
    """Procura o Excel do modo online tanto na raiz (BASE) como na pasta dados/."""
    for pasta in (BASE, os.path.join(BASE, "dados")):
        caminho_exato = os.path.join(pasta, "Jogadores e Estatísticas ModoOnline.xlsx")
        if os.path.isfile(caminho_exato):
            return caminho_exato
        if os.path.isdir(pasta):
            for nome_fich in os.listdir(pasta):
                if nome_fich.lower().endswith(".xlsx") and "modoonline" in _norm(nome_fich):
                    return os.path.join(pasta, nome_fich)
    raise FileNotFoundError("Excel do modo online ('Jogadores e Estatísticas ModoOnline.xlsx') não encontrado.")

def carregar_jogadores():
    """Tabela 1 (cols A-C): guarda-redes. Tabela 2 (cols E-L): jogadores de linha. Sorteio = todas as linhas lidas."""
    df, out = pd.read_excel(_xlsx("Jogadores_e_Estatísticas")), []
    for _, r in df.iloc[:, 0:3][df.iloc[:, 0].notna()].iterrows():
        out.append(me.Jogador(str(r.iloc[0]).strip(), ["Guarda-redes"], {"gr": int(r.iloc[2])}))
    for _, r in df.iloc[:, 4:12][df.iloc[:, 4].notna()].iterrows():
        pos = [p.strip() for p in str(r.iloc[1]).split("/")]
        out.append(me.Jogador(str(r.iloc[0]).strip(), pos, dict(zip(me.KEYS, [int(x) for x in r.iloc[2:8]]))))
    return out

def carregar_jogadores_online():
    """Lê o plantel completo do Excel dedicado ao motor online."""
    caminho = _xlsx_online()
    df = pd.read_excel(caminho)
    campos = {
        "Reflexos": "reflexos", "Comando de Área": "comando_area", "Jogo Aéreo": "jogo_aereo",
        "Um para Um": "um_para_um", "Pontapé de Baliza": "pontape_baliza", "Lançamento": "lancamento",
        "Bola Parada": "bola_parada", "Cruzamento": "cruzamento", "Drible": "drible",
        "Finalização": "finalizacao", "Cabeceamento": "cabecemento", "Passe": "passe",
        "Primeiro Toque": "primeiro_toque", "Técnica": "tecnica", "Desarme": "desarme",
        "Marcação": "marcacao", "Antecipação": "antecipacao", "Decisões": "decisoes",
        "Visão de Jogo": "visao", "Concentração": "concentracao", "Agressividade": "agressividade",
        "Bravura": "bravura", "Compostura": "compostura", "Índice de Trabalho": "trabalho",
        "Posicionamento": "posicionamento", "Sem Bola": "sem_bola", "Aceleração": "aceleracao",
        "Velocidade": "velocidade", "Agilidade": "agilidade", "Equilíbrio": "equilibrio",
        "Força": "forca", "Impulsão": "impulsao", "Resistência": "resistencia",
    }
    rotulos = {"GR": "Guarda-redes", "D": "Defesa", "M": "Médio", "A": "Avançado"}
    out = []
    for _, row in df.iterrows():
        if pd.isna(row.get("Nome")):
            continue
        nome = str(row["Nome"]).strip()
        codigos = [x.strip().upper() for x in str(row.get("Posição(ões)", "")).split("/") if x.strip()]
        pos = [rotulos[x] for x in codigos if x in rotulos]
        atributos = {}
        for coluna, chave in campos.items():
            valor = row.get(coluna, 50)
            atributos[chave] = float(valor) if pd.notna(valor) else 50.0
        altura = row.get("Altura(m)", 1.78)
        pe_fraco = row.get("Habilidade Com o Pé Fraco (1 a 5)", 3)
        atributos["altura"] = float(altura) if pd.notna(altura) else 1.78
        atributos["pe_preferido"] = str(row.get("Pé Preferido", "Direito"))
        atributos["pe_fraco"] = float(pe_fraco) if pd.notna(pe_fraco) else 3.0
        tracos = row.get("Traços", "")
        atributos["traits"] = "" if pd.isna(tracos) else str(tracos)
        atributos["gr"] = (0.28 * atributos["reflexos"] + 0.24 * atributos["um_para_um"]
                            + 0.14 * atributos["jogo_aereo"] + 0.12 * atributos["comando_area"]
                            + 0.10 * atributos["concentracao"] + 0.08 * atributos["posicionamento"]
                            + 0.04 * atributos["decisoes"])
        out.append(me.Jogador(nome, pos, atributos))
    return out

def carregar_equipas():
    df = pd.read_excel(_xlsx("Lista_de_equipas"))
    return [(str(a).strip(), float(b)) for a, b in zip(df.iloc[:, 0], df.iloc[:, 1]) if pd.notna(a)]

def pub(j, i): return {"id": i, "nome": j.nome, "pos": " / ".join(j.pos)}   # NUNCA envia atributos
def sortear(pool): return random.sample(sorted(pool), min(5, len(pool)))
def nome_ok(n):
    if not isinstance(n, str): return None
    n = n.strip()
    return n if 2 <= len(n) <= 20 else None

# ---------- Ranking global (SQLite) ----------
def db():
    c = sqlite3.connect(DB)
    c.execute("CREATE TABLE IF NOT EXISTS r(id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, pts INT, gd INT, gf INT)")
    return c

def gravar_e_ranking(nome, pts, gd, gf):
    c = db(); cur = c.execute("INSERT INTO r(nome,pts,gd,gf) VALUES(?,?,?,?)", (nome, pts, gd, gf)); rid = cur.lastrowid
    lugar = 1 + c.execute("SELECT COUNT(*) FROM r WHERE pts>? OR (pts=? AND gd>?) OR (pts=? AND gd=? AND gf>?) OR (pts=? AND gd=? AND gf=? AND id<?)",
                          (pts, pts, gd, pts, gd, gf, pts, gd, gf, rid)).fetchone()[0]
    top = [dict(nome=n, pts=p, gd=g, gf=f) for n, p, g, f in c.execute("SELECT nome,pts,gd,gf FROM r ORDER BY pts DESC,gd DESC,gf DESC,id LIMIT 10")]
    c.commit(); c.close()
    return top, lugar

# ---------- Rotas ----------
@app.route("/")
def index(): return render_template("index.html")

@app.get("/healthz")
def healthz():
    missing = []
    for prefix, expected in (("Jogadores_e_Estatísticas", "Jogadores_e_Estatísticas.xlsx"),
                             ("Lista_de_equipas", "Lista_de_equipas_e_Força.xlsx")):
        try:
            _xlsx(prefix)
        except FileNotFoundError:
            missing.append(expected)
    try:
        _xlsx_online()
    except FileNotFoundError:
        missing.append("Jogadores e Estatísticas ModoOnline.xlsx")
    if missing:
        return jsonify(ok=False, missing=missing), 503
    return jsonify(ok=True)

@app.route("/musica.mp3")
@app.route("/static/musica.mp3")
def servir_musica():
    for pasta in (BASE, os.path.join(BASE, "static"), os.path.join(BASE, "dados")):
        p = os.path.join(pasta, "musica.mp3")
        if os.path.isfile(p):
            return send_file(p, mimetype="audio/mpeg", conditional=True)
        for f in glob.glob(os.path.join(pasta, "*.mp3")):
            return send_file(f, mimetype="audio/mpeg", conditional=True)
    return "", 404

@app.route("/api/coord")
def coord():
    return jsonify(
        coord=me.COORD,
        form={k: [r[0] for r in v] for k, v in me.FORM.items()},
        posicoes=online_me.POSITION_LAYOUT,
        funcoes=online_me.ROLE_OPTIONS_BY_POSITION,
        catalogo_funcoes=online_me.ROLE_CATALOG,
    )

@app.post("/api/offline/novo")
def off_novo():
    d = request.get_json(silent=True)
    nome = nome_ok(d.get("nome")) if isinstance(d, dict) else None
    if not nome: return jsonify(erro="Escreve o teu nome (2 a 20 letras)."), 400
    tk = uuid.uuid4().hex; jog = carregar_jogadores()
    OFF[tk] = dict(nome=nome, jog=jog, pool=set(range(len(jog))), picks=[])
    OFF[tk]["oferta"] = sortear(OFF[tk]["pool"])
    return jsonify(token=tk, oferta=[pub(jog[i], i) for i in OFF[tk]["oferta"]], n=0, picks=[])

@app.post("/api/offline/escolher")
def off_escolher():
    d = request.get_json(silent=True)
    if not isinstance(d, dict): return jsonify(erro="Escolha inválida."), 400
    token = d.get("token")
    g = OFF.get(token) if isinstance(token, str) else None
    if not g or type(d.get("id")) is not int or d["id"] not in g["oferta"]: return jsonify(erro="Escolha inválida."), 400
    g["picks"].append(d["id"]); g["pool"].discard(d["id"])
    escolhidos = [pub(g["jog"][i], i) for i in g["picks"]]
    if len(g["picks"]) == 7:
        return jsonify(fim=True, plantel=escolhidos, picks=escolhidos)
    g["oferta"] = sortear(g["pool"])
    return jsonify(oferta=[pub(g["jog"][i], i) for i in g["oferta"]], n=len(g["picks"]), picks=escolhidos)

@app.post("/api/offline/simular")
def off_simular():
    d = request.get_json(silent=True)
    if not isinstance(d, dict): return jsonify(erro="Dados inválidos."), 400
    token = d.get("token")
    g = OFF.get(token) if isinstance(token, str) else None
    linha, tat = d.get("linha", []), d.get("tatica")
    if not g or type(tat) is not int or tat not in (1, 2, 3) or not isinstance(linha, list) or any(type(i) is not int for i in linha) or sorted(linha) != sorted(g["picks"]): return jsonify(erro="Dados inválidos."), 400
    ef = me.montar([g["jog"][i] for i in linha], tat)
    tab, marc, jogos = me.simular_liga_offline(ef, tat, carregar_equipas())
    u = next(t for t in tab if t["equipa"] == "AC Travanca")
    top, lugar = gravar_e_ranking(g["nome"], u["pts"], u["gd"], u["gm"]); OFF.pop(d["token"], None)
    tab = [{k: t[k] for k in ("equipa", "j", "v", "e", "d", "gm", "gs", "gd", "pts")} for t in tab]   # sem forças
    return jsonify(tabela=tab, marcadores=[m for m in marc if m[1] > 0], jogos=jogos, top10=top, lugar=lugar, nome=g["nome"])

# ---------- Online (Flask-SocketIO) ----------
def estado(sid, s):
    r = SALAS[s]; eu = r["p"][sid]; adv = r["p"][r["ordem"][1 - r["ordem"].index(sid)]] if len(r["ordem"]) == 2 else None
    vez = r["fase"] == "draft" and r["ordem"][r["vez"]] == sid
    return dict(fase=r["fase"], minha_vez=vez, vez_de=r["p"][r["ordem"][r["vez"]]]["nome"] if len(r["ordem"]) == 2 else "",
                oferta=[pub(r["jog"][i], i) for i in r["oferta"]] if r["fase"] == "draft" else [],
                meus=[pub(r["jog"][i], i) for i in eu["picks"]], adv=adv["nome"] if adv else "",
                n_adv=len(adv["picks"]) if adv else 0, adv_picks=[pub(r["jog"][i], i) for i in adv["picks"]] if adv else [])

def difundir(s):
    for sid in SALAS[s]["ordem"]: emit("estado", estado(sid, s), to=sid)

@app.post("/api/sala")
def criar_sala():
    try:
        jog = carregar_jogadores_online()
    except FileNotFoundError:
        app.logger.exception("Falta o ficheiro Excel do plantel online")
        return jsonify(erro="Falta o ficheiro 'Jogadores e Estatísticas ModoOnline.xlsx' (na raiz ou na pasta dados/) no projeto publicado no GitHub/Render."), 503
    except Exception:
        app.logger.exception("Não foi possível ler o Excel do plantel online")
        return jsonify(erro="Não foi possível ler o plantel online. Confirma o Excel e os logs de build do Render."), 503
    if len(jog) < 14:
        return jsonify(erro="O plantel online precisa de pelo menos 14 jogadores."), 503
    s = str(uuid.uuid4())
    with SALAS_LOCK:
        SALAS[s] = dict(p={}, ordem=[], fase="espera", jog=jog, vez=0, oferta=[], pool=set(range(len(jog))))
    return jsonify(sala=s)

@socketio.on("entrar")
def on_entrar(d):
    d = d if isinstance(d, dict) else {}
    s, nome = d.get("sala"), nome_ok(d.get("nome")); sid = request.sid
    if not isinstance(s, str): return emit("erro", "Sala inválida ou expirada.")
    jogador = d.get("jogador")
    if not isinstance(jogador, str) or not 8 <= len(jogador) <= 64: jogador = sid
    if not nome: return emit("erro", "Escreve o teu nome (2 a 20 letras).")
    with SALAS_LOCK:
        r = SALAS.get(s)
        if not r: return emit("erro", "Sala inválida ou expirada. Verifica se o Render está configurado com 1 worker (-w 1).")
        r["ordem"] = [p_sid for p_sid in r["ordem"] if p_sid in r["p"]]
        anterior = next((p_sid for p_sid, p in r["p"].items() if p.get("jogador") == jogador), None)
        lugar_abandonado = None if anterior is not None else next(
            (p_sid for p_sid in r["ordem"] if not r["p"][p_sid].get("ligado", True)), None)
        substituir = anterior if anterior is not None else lugar_abandonado
        if substituir is not None and substituir != sid:
            p = r["p"].pop(substituir)
            if substituir in r["ordem"]:
                r["ordem"][r["ordem"].index(substituir)] = sid
            else:
                r["ordem"].append(sid)
            leave_room(s, sid=substituir)
            p.update(nome=nome, jogador=jogador, ligado=True)
            r["p"][sid] = p
        elif anterior is None:
            if len(r["ordem"]) >= 2: return emit("erro", "Sala cheia. Esta sala já tem dois jogadores.")
            r["p"][sid] = dict(nome=nome, jogador=jogador, ligado=True, picks=[], tat=None, linha=None, funcoes=None, sala=s)
            r["ordem"].append(sid)
            if len(r["ordem"]) == 2:
                random.shuffle(r["ordem"]); r["fase"] = "draft"; r["oferta"] = sortear(r["pool"])
        r["p"][sid].update(nome=nome, jogador=jogador, ligado=True)
        if sid not in r["ordem"]: r["ordem"].append(sid)
        join_room(s)
        difundir(s)

def _expirar_desconexao(s, sid, jogador):
    socketio.sleep(25)
    with SALAS_LOCK:
        r = SALAS.get(s); p = r["p"].get(sid) if r else None
        if not p or p.get("jogador") != jogador or p.get("ligado", True): return
        SALAS.pop(s, None)
    socketio.emit("saiu", {}, to=s)

@socketio.on("escolher")
def on_escolher(d):
    d = d if isinstance(d, dict) else {}
    sid = request.sid
    with SALAS_LOCK:
        me_ = next((r for r in SALAS.values() if sid in r["p"]), None)
        if not me_ or me_["fase"] != "draft" or me_["ordem"][me_["vez"]] != sid or type(d.get("id")) is not int or d["id"] not in me_["oferta"]: return
        me_["p"][sid]["picks"].append(d["id"]); me_["pool"].discard(d["id"])   # sai do sorteio para ambos
        if all(len(p["picks"]) == 7 for p in me_["p"].values()): me_["fase"] = "tatica"
        else: me_["vez"] = 1 - me_["vez"]; me_["oferta"] = sortear(me_["pool"])
        s = me_["p"][sid]["sala"]; difundir(s)

@socketio.on("mudar_tatica")
def on_mudar_tatica():
    sid = request.sid
    with SALAS_LOCK:
        r = next((r for r in SALAS.values() if sid in r["p"]), None)
        if not r or r["fase"] != "tatica": return
        r["p"][sid]["tat"], r["p"][sid]["linha"], r["p"][sid]["funcoes"] = None, None, None

@socketio.on("formacao")
def on_formacao(d):
    d = d if isinstance(d, dict) else {}
    sid = request.sid
    with SALAS_LOCK:
        r = next((r for r in SALAS.values() if sid in r["p"]), None)
        if not r or r["fase"] != "tatica": return
        p = r["p"][sid]
        linha, tatica = d.get("linha", []), d.get("tatica")
        if type(tatica) is not int or tatica not in (1, 2, 3) or not isinstance(linha, list) or any(type(i) is not int for i in linha) or sorted(linha) != sorted(p["picks"]): return
        funcoes = online_me.validar_funcoes(tatica, d.get("funcoes"))
        p["tat"], p["linha"], p["funcoes"] = tatica, linha, funcoes
        if all(x["tat"] for x in r["p"].values()):
            a, b = (r["p"][i] for i in r["ordem"])
            fn_a = online_me.validar_funcoes(a["tat"], a.get("funcoes"))
            fn_b = online_me.validar_funcoes(b["tat"], b.get("funcoes"))
            ev, st = me.match_engine_online(
                a["nome"], b["nome"],
                [r["jog"][i] for i in a["linha"]],
                [r["jog"][i] for i in b["linha"]],
                a["tat"], b["tat"],
                fn_a, fn_b,
            )
            print(me._gerar_tabela_consola(a["nome"], b["nome"], st))
            eq = [
                dict(
                    nome=x["nome"],
                    tat=x["tat"],
                    jog=[r["jog"][i].nome for i in x["linha"]],
                    posicoes=online_me.POSITION_LAYOUT[x["tat"]],
                    funcoes=fn,
                    funcoes_curtas=[online_me.ROLE_CATALOG[f]["curto"] for f in fn],
                    funcoes_nomes=[online_me.ROLE_CATALOG[f]["nome"] for f in fn],
                )
                for x, fn in ((a, fn_a), (b, fn_b))
            ]
            emit("jogo", dict(eventos=ev, stats=st, equipas=eq), to=a["sala"]); SALAS.pop(a["sala"], None)   # reset da sala
        else: emit("espera", {}, to=sid)

@socketio.on("disconnect")
def on_disc():
    sid = request.sid
    with SALAS_LOCK:
        for s, r in list(SALAS.items()):
            p = r["p"].get(sid)
            if p:
                p["ligado"] = False
                socketio.emit("desconectado", {}, to=s)
                socketio.start_background_task(_expirar_desconexao, s, sid, p["jogador"])
                return

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), allow_unsafe_werkzeug=True)

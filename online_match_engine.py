"""Simulador online espacial do AC Travanca.

O motor offline continua em match_engine.py. Este motor usa os atributos do
Excel ModoOnline, posicionamento contínuo em metros, funções táticas por jogador
e uma bola com trajetória.
"""
import math
import random


POSITION_LAYOUT = {
    1: ["GR", "D", "D", "MC", "ML", "ML", "A"],
    2: ["GR", "DL", "DL", "DC", "MC", "AW", "AW"],
    # Os centrais ficam explicitamente nas posições numeradas 2 e 4.
    3: ["GR", "D", "MIX", "D", "MIX", "AW", "AW"],
}

OUTFIELD_ATTRIBUTES = (
    "bola_parada", "cruzamento", "drible", "finalizacao", "cabecemento", "passe",
    "primeiro_toque", "tecnica", "desarme", "marcacao", "antecipacao", "decisoes",
    "visao", "concentracao", "agressividade", "bravura", "compostura", "trabalho",
    "posicionamento", "sem_bola", "aceleracao", "velocidade", "agilidade", "equilibrio",
    "forca", "impulsao", "resistencia",
)
GOALKEEPER_ATTRIBUTES = ("reflexos", "comando_area", "jogo_aereo", "um_para_um", "pontape_baliza", "lancamento")
ALL_ATTRIBUTES = OUTFIELD_ATTRIBUTES + GOALKEEPER_ATTRIBUTES
DEFENDER_POSITIONS = {"D", "DC", "DL"}
MIDFIELD_POSITIONS = {"MC", "ML", "MIX"}
FORWARD_POSITIONS = {"A", "AW"}

# Cada posição recebe um peso base para todos os atributos e pesos maiores
# para os mais úteis. Assim, um atributo secundário continua a contar.
POSITION_NEEDS = {
    "GR": {"reflexos": 5, "um_para_um": 5, "comando_area": 4, "jogo_aereo": 3, "posicionamento": 3, "concentracao": 2, "decisoes": 2, "pontape_baliza": 2, "lancamento": 2, "agilidade": 2, "bravura": 1, "forca": 1, "passe": 1},
    "D": {"desarme": 4, "marcacao": 4, "antecipacao": 4, "posicionamento": 4, "concentracao": 3, "decisoes": 3, "bravura": 3, "forca": 3, "cabecemento": 2, "impulsao": 2, "resistencia": 2, "velocidade": 2, "passe": 1},
    "DC": {"desarme": 4, "marcacao": 4, "antecipacao": 4, "posicionamento": 4, "concentracao": 3, "decisoes": 3, "bravura": 3, "forca": 3, "cabecemento": 3, "impulsao": 3, "resistencia": 2, "passe": 1},
    "DL": {"desarme": 3, "marcacao": 3, "antecipacao": 2, "posicionamento": 2, "resistencia": 3, "velocidade": 4, "aceleracao": 4, "cruzamento": 3, "drible": 2, "trabalho": 3, "passe": 2, "agilidade": 2},
    "MC": {"passe": 4, "visao": 4, "decisoes": 4, "primeiro_toque": 3, "tecnica": 3, "trabalho": 3, "resistencia": 3, "antecipacao": 2, "marcacao": 2, "posicionamento": 2, "drible": 2},
    "ML": {"cruzamento": 4, "drible": 4, "aceleracao": 4, "velocidade": 4, "tecnica": 3, "primeiro_toque": 3, "sem_bola": 3, "resistencia": 2, "passe": 2, "finalizacao": 2},
    "MIX": {"passe": 3, "visao": 3, "decisoes": 3, "primeiro_toque": 3, "tecnica": 3, "trabalho": 3, "resistencia": 3, "cruzamento": 2, "drible": 2, "velocidade": 2, "antecipacao": 2},
    "A": {"finalizacao": 5, "sem_bola": 4, "compostura": 4, "primeiro_toque": 3, "cabecemento": 3, "aceleracao": 3, "velocidade": 3, "decisoes": 2, "tecnica": 2, "forca": 2},
    "AW": {"drible": 4, "aceleracao": 4, "velocidade": 4, "tecnica": 3, "cruzamento": 3, "sem_bola": 3, "primeiro_toque": 3, "finalizacao": 3, "passe": 2, "agilidade": 2},
}

# Catálogo detalhado de funções táticas:
# - needs: pesos extra somados aos atributos-chave da função (sem anular os restantes atributos)
# - advance / def_advance: deslocamento longitudinal em posse e sem posse
# - width: ajuste de largura (>0 abre na ala, <0 fecha por dentro)
# - pass_w, dribble_w, shot_w, cross_w: multiplicadores de decisão com bola
# - through_bias: tendência adicional para procurar passes de rutura
# - receive_pass_w, receive_through_w, receive_cross_w: tendência para receber cada tipo de bola
# - intercept_bonus, duel_bonus: impacto defensivo na leitura de passe e no 1x1
ROLE_DEFINITIONS = {
    # ---------- GUARDA-REDES (GR) ----------
    "gr_classico": {
        "id": "gr_classico",
        "nome": "Guarda-Redes Clássico",
        "curto": "GR Clássico",
        "desc": "Focado na defesa entre os postes e no controlo da pequena área, jogando seguro.",
        "atributos": "Reflexos, Posicionamento, Um para Um, Concentração, Jogo Aéreo",
        "needs": {"reflexos": 5, "posicionamento": 4, "um_para_um": 4, "concentracao": 4, "jogo_aereo": 3, "comando_area": 3},
        "advance": 0.0, "def_advance": 0.0, "width": 0.0,
        "pass_w": 1.0, "dribble_w": 1.0, "shot_w": 1.0, "cross_w": 1.0,
        "through_bias": -0.04, "receive_pass_w": 1.0, "receive_through_w": 1.0, "receive_cross_w": 1.0,
        "intercept_bonus": 0.0, "duel_bonus": 0.0,
    },
    "gr_libero": {
        "id": "gr_libero",
        "nome": "Guarda-Redes Líbero",
        "curto": "GR Líbero",
        "desc": "Sai da baliza para varrer bolas nas costas da defesa e inicia contra-ataques com passes longos.",
        "atributos": "Um para Um, Reflexos, Antecipação, Decisões, Pontapé de Baliza, Lançamento",
        "needs": {"um_para_um": 5, "reflexos": 4, "antecipacao": 4, "decisoes": 4, "pontape_baliza": 4, "lancamento": 4, "passe": 3, "aceleracao": 3},
        "advance": 0.022, "def_advance": 0.018, "width": 0.0,
        "pass_w": 1.15, "dribble_w": 1.0, "shot_w": 1.0, "cross_w": 1.0,
        "through_bias": 0.14, "receive_pass_w": 1.0, "receive_through_w": 1.0, "receive_cross_w": 1.0,
        "intercept_bonus": 0.08, "duel_bonus": 1.5,
    },

    # ---------- DEFESAS CENTRAIS (D / DC) ----------
    "dc_destruidor": {
        "id": "dc_destruidor",
        "nome": "Central Destruidor",
        "curto": "Destruidor",
        "desc": "Agressivo a atacar o portador da bola, dominante no choque físico e no jogo aéreo.",
        "atributos": "Desarme, Marcação, Força, Agressividade, Bravura, Cabeceamento",
        "needs": {"desarme": 5, "marcacao": 5, "forca": 5, "bravura": 4, "agressividade": 3, "cabecemento": 4, "impulsao": 4},
        "advance": 0.015, "def_advance": 0.095, "width": 0.0,
        "pass_w": 1.05, "dribble_w": 0.75, "shot_w": 0.8, "cross_w": 0.7,
        "through_bias": -0.05, "receive_pass_w": 0.90, "receive_through_w": 0.75, "receive_cross_w": 1.25,
        "intercept_bonus": 0.02, "duel_bonus": 4.2,
    },
    "dc_construtor": {
        "id": "dc_construtor",
        "nome": "Central Construtor",
        "curto": "Construtor",
        "desc": "Sai a jogar com critério desde trás, quebrando linhas com passes verticais e visão.",
        "atributos": "Passe, Visão de Jogo, Compostura, Decisões, Primeiro Toque, Posicionamento",
        "needs": {"passe": 5, "visao": 5, "compostura": 4, "decisoes": 4, "primeiro_toque": 4, "tecnica": 3, "posicionamento": 3, "desarme": 3},
        "advance": 0.045, "def_advance": 0.065, "width": 0.01,
        "pass_w": 1.32, "dribble_w": 1.05, "shot_w": 0.85, "cross_w": 0.8,
        "through_bias": 0.14, "receive_pass_w": 1.22, "receive_through_w": 0.85, "receive_cross_w": 1.0,
        "intercept_bonus": 0.04, "duel_bonus": 1.0,
    },
    "dc_cobertura": {
        "id": "dc_cobertura",
        "nome": "Central de Cobertura",
        "curto": "Cobertura",
        "desc": "Posiciona-se mais recuado para ler a profundidade, cortar passes e dobrar os colegas.",
        "atributos": "Antecipação, Posicionamento, Concentração, Velocidade, Aceleração, Decisões",
        "needs": {"antecipacao": 5, "posicionamento": 5, "concentracao": 4, "velocidade": 4, "aceleracao": 4, "decisoes": 4, "desarme": 3},
        "advance": 0.008, "def_advance": 0.035, "width": -0.01,
        "pass_w": 1.15, "dribble_w": 0.80, "shot_w": 0.75, "cross_w": 0.7,
        "through_bias": 0.0, "receive_pass_w": 0.95, "receive_through_w": 0.70, "receive_cross_w": 0.95,
        "intercept_bonus": 0.12, "duel_bonus": 2.2,
    },

    # ---------- DEFESAS LATERAIS NA TÁTICA 2 · 3-1-2 (DL) ----------
    "dl_ala_completo": {
        "id": "dl_ala_completo",
        "nome": "Ala Completo",
        "curto": "Ala Completo",
        "desc": "Faz o corredor inteiro no 3-1-2: dá largura máxima ao ataque, cruza e recupera a defender.",
        "atributos": "Velocidade, Aceleração, Resistência, Índice de Trabalho, Cruzamento, Desarme",
        "needs": {"velocidade": 5, "aceleracao": 5, "resistencia": 5, "trabalho": 4, "cruzamento": 4, "drible": 3, "desarme": 3},
        "advance": 0.095, "def_advance": 0.055, "width": 0.105,
        "pass_w": 1.0, "dribble_w": 1.25, "shot_w": 0.95, "cross_w": 1.65,
        "through_bias": 0.04, "receive_pass_w": 1.15, "receive_through_w": 1.28, "receive_cross_w": 0.95,
        "intercept_bonus": 0.04, "duel_bonus": 2.0,
    },
    "dl_defensivo": {
        "id": "dl_defensivo",
        "nome": "Lateral Defensivo",
        "curto": "Lat. Defensivo",
        "desc": "Fecha o flanco e mantém o trio defensivo compacto no 3-1-2, arriscando pouco na subida.",
        "atributos": "Desarme, Marcação, Posicionamento, Antecipação, Força, Concentração",
        "needs": {"desarme": 5, "marcacao": 5, "posicionamento": 5, "antecipacao": 4, "forca": 4, "concentracao": 4, "bravura": 3},
        "advance": 0.020, "def_advance": 0.080, "width": 0.035,
        "pass_w": 1.22, "dribble_w": 0.72, "shot_w": 0.65, "cross_w": 0.65,
        "through_bias": -0.04, "receive_pass_w": 0.92, "receive_through_w": 0.72, "receive_cross_w": 0.80,
        "intercept_bonus": 0.10, "duel_bonus": 3.8,
    },
    "dl_invertido": {
        "id": "dl_invertido",
        "nome": "Lateral Invertido (Interior)",
        "curto": "Lat. Invertido",
        "desc": "Em posse fecha por dentro ao lado do MC para dar superioridade no meio e lançar passes de rutura.",
        "atributos": "Passe, Visão de Jogo, Decisões, Primeiro Toque, Técnica, Antecipação",
        "needs": {"passe": 5, "visao": 5, "decisoes": 4, "primeiro_toque": 4, "tecnica": 4, "antecipacao": 3, "posicionamento": 3, "trabalho": 3},
        "advance": 0.068, "def_advance": 0.060, "width": -0.065,
        "pass_w": 1.38, "dribble_w": 1.05, "shot_w": 1.05, "cross_w": 0.75,
        "through_bias": 0.16, "receive_pass_w": 1.30, "receive_through_w": 1.05, "receive_cross_w": 0.80,
        "intercept_bonus": 0.07, "duel_bonus": 1.8,
    },
    "dl_ofensivo": {
        "id": "dl_ofensivo",
        "nome": "Ala Ofensivo Projetado",
        "curto": "Ala Ofensivo",
        "desc": "Ataca constantemente a linha de fundo como um extremo extra no 3-1-2, procurando 1x1 e cruzamentos.",
        "atributos": "Aceleração, Velocidade, Drible, Cruzamento, Técnica, Sem Bola",
        "needs": {"aceleracao": 5, "velocidade": 5, "drible": 5, "cruzamento": 5, "tecnica": 4, "sem_bola": 4, "finalizacao": 3},
        "advance": 0.135, "def_advance": 0.030, "width": 0.10,
        "pass_w": 0.90, "dribble_w": 1.48, "shot_w": 1.25, "cross_w": 1.85,
        "through_bias": 0.06, "receive_pass_w": 1.18, "receive_through_w": 1.45, "receive_cross_w": 1.10,
        "intercept_bonus": -0.02, "duel_bonus": 0.5,
    },

    # ---------- MÉDIOS LATERAIS NA TÁTICA 1 · 2-3-1 (ML) ----------
    "ml_extremo_puro": {
        "id": "ml_extremo_puro",
        "nome": "Extremo Clássico (Linha)",
        "curto": "Ext. Clássico",
        "desc": "Cola-se à linha lateral no 2-3-1, encara o defesa em velocidade e cruza para a área.",
        "atributos": "Cruzamento, Velocidade, Aceleração, Drible, Técnica, Agilidade",
        "needs": {"cruzamento": 5, "velocidade": 5, "aceleracao": 5, "drible": 5, "tecnica": 4, "agilidade": 4, "sem_bola": 3},
        "advance": 0.115, "def_advance": 0.0, "width": 0.110,
        "pass_w": 0.92, "dribble_w": 1.45, "shot_w": 1.05, "cross_w": 1.85,
        "through_bias": 0.03, "receive_pass_w": 1.15, "receive_through_w": 1.42, "receive_cross_w": 1.05,
        "intercept_bonus": 0.0, "duel_bonus": 1.0,
    },
    "ml_extremo_invertido": {
        "id": "ml_extremo_invertido",
        "nome": "Extremo Invertido (Diagonal)",
        "curto": "Ext. Invertido",
        "desc": "Parte da ala em diagonal para o centro no 2-3-1 para rematar à baliza ou atacar a área.",
        "atributos": "Drible, Finalização, Técnica, Aceleração, Compostura, Sem Bola",
        "needs": {"drible": 5, "finalizacao": 5, "tecnica": 4, "aceleracao": 4, "compostura": 4, "sem_bola": 4, "velocidade": 3, "primeiro_toque": 3},
        "advance": 0.130, "def_advance": 0.0, "width": -0.065,
        "pass_w": 0.90, "dribble_w": 1.42, "shot_w": 1.60, "cross_w": 0.78,
        "through_bias": 0.08, "receive_pass_w": 1.15, "receive_through_w": 1.50, "receive_cross_w": 1.38,
        "intercept_bonus": 0.0, "duel_bonus": 1.0,
    },
    "ml_ala_equilibrado": {
        "id": "ml_ala_equilibrado",
        "nome": "Médio Ala Trabalhador",
        "curto": "Ala Equilibrado",
        "desc": "Fecha o corredor defensivo para ajudar a dupla de centrais do 2-3-1 e sai rápido na transição.",
        "atributos": "Resistência, Índice de Trabalho, Desarme, Posicionamento, Velocidade, Cruzamento",
        "needs": {"resistencia": 5, "trabalho": 5, "desarme": 4, "posicionamento": 4, "velocidade": 4, "cruzamento": 3, "passe": 3, "antecipacao": 3},
        "advance": 0.070, "def_advance": -0.045, "width": 0.075,
        "pass_w": 1.15, "dribble_w": 1.05, "shot_w": 0.88, "cross_w": 1.30,
        "through_bias": 0.02, "receive_pass_w": 1.10, "receive_through_w": 1.12, "receive_cross_w": 0.95,
        "intercept_bonus": 0.08, "duel_bonus": 3.0,
    },
    "ml_criativo_interior": {
        "id": "ml_criativo_interior",
        "nome": "Organizador Aberto (Meia-Ala)",
        "curto": "Org. Aberto",
        "desc": "Deriva da ala para entrelinhas para associar-se ao MC e meter passes de rutura.",
        "atributos": "Passe, Visão de Jogo, Decisões, Técnica, Primeiro Toque, Compostura",
        "needs": {"passe": 5, "visao": 5, "decisoes": 5, "tecnica": 4, "primeiro_toque": 4, "compostura": 3, "cruzamento": 3, "drible": 3},
        "advance": 0.090, "def_advance": -0.010, "width": -0.045,
        "pass_w": 1.40, "dribble_w": 1.12, "shot_w": 1.05, "cross_w": 1.15,
        "through_bias": 0.18, "receive_pass_w": 1.35, "receive_through_w": 1.15, "receive_cross_w": 0.90,
        "intercept_bonus": 0.03, "duel_bonus": 1.2,
    },

    # ---------- MÉDIO CENTRO (MC) ----------
    "mc_organizador": {
        "id": "mc_organizador",
        "nome": "Organizador de Jogo",
        "curto": "Organizador",
        "desc": "Cérebro do meio-campo: pede sempre a bola, dita o ritmo e descobre linhas de passe.",
        "atributos": "Passe, Visão de Jogo, Decisões, Primeiro Toque, Técnica, Compostura",
        "needs": {"passe": 5, "visao": 5, "decisoes": 5, "primeiro_toque": 4, "tecnica": 4, "compostura": 4, "posicionamento": 3},
        "advance": 0.055, "def_advance": 0.0, "width": 0.0,
        "pass_w": 1.42, "dribble_w": 0.95, "shot_w": 0.92, "cross_w": 1.0,
        "through_bias": 0.18, "receive_pass_w": 1.38, "receive_through_w": 0.95, "receive_cross_w": 0.85,
        "intercept_bonus": 0.04, "duel_bonus": 1.2,
    },
    "mc_trinco": {
        "id": "mc_trinco",
        "nome": "Trinco Posicional",
        "curto": "Trinco",
        "desc": "Ancora o meio-campo à frente da defesa, fecha linhas de passe e recupera bolas.",
        "atributos": "Posicionamento, Desarme, Antecipação, Marcação, Concentração, Força",
        "needs": {"posicionamento": 5, "desarme": 5, "antecipacao": 5, "marcacao": 4, "concentracao": 4, "forca": 4, "trabalho": 3, "passe": 3},
        "advance": 0.020, "def_advance": -0.035, "width": 0.0,
        "pass_w": 1.25, "dribble_w": 0.72, "shot_w": 0.70, "cross_w": 0.75,
        "through_bias": -0.02, "receive_pass_w": 1.12, "receive_through_w": 0.70, "receive_cross_w": 0.80,
        "intercept_bonus": 0.12, "duel_bonus": 3.8,
    },
    "mc_box_to_box": {
        "id": "mc_box_to_box",
        "nome": "Box-to-Box (Todo-o-Terreno)",
        "curto": "Box-to-Box",
        "desc": "Percorre o campo de área a área: pressiona na recuperação e chega de trás para finalizar.",
        "atributos": "Resistência, Índice de Trabalho, Velocidade, Passe, Desarme, Sem Bola",
        "needs": {"resistencia": 5, "trabalho": 5, "velocidade": 4, "passe": 3, "desarme": 4, "sem_bola": 4, "finalizacao": 3, "forca": 3},
        "advance": 0.095, "def_advance": -0.015, "width": 0.0,
        "pass_w": 1.10, "dribble_w": 1.15, "shot_w": 1.30, "cross_w": 1.0,
        "through_bias": 0.06, "receive_pass_w": 1.20, "receive_through_w": 1.28, "receive_cross_w": 1.18,
        "intercept_bonus": 0.06, "duel_bonus": 2.8,
    },
    "mc_ofensivo": {
        "id": "mc_ofensivo",
        "nome": "Médio Ofensivo (Criativo #10)",
        "curto": "Médio Ofensivo",
        "desc": "Joga adiantado no apoio aos avançados para rasgar a defesa com drible, último passe ou remate.",
        "atributos": "Visão de Jogo, Técnica, Passe, Drible, Decisões, Finalização",
        "needs": {"visao": 5, "tecnica": 5, "passe": 4, "drible": 4, "decisoes": 4, "finalizacao": 4, "primeiro_toque": 4, "sem_bola": 3},
        "advance": 0.120, "def_advance": 0.020, "width": 0.0,
        "pass_w": 1.18, "dribble_w": 1.38, "shot_w": 1.42, "cross_w": 1.05,
        "through_bias": 0.16, "receive_pass_w": 1.32, "receive_through_w": 1.35, "receive_cross_w": 1.10,
        "intercept_bonus": -0.01, "duel_bonus": 0.6,
    },

    # ---------- MÉDIOS INTERIORES / HÍBRIDOS NA TÁTICA 3 · 2-2-2 (MIX) ----------
    "mix_interior": {
        "id": "mix_interior",
        "nome": "Médio Interior (Mezzala)",
        "curto": "Mezzala",
        "desc": "Ataca os meios-espaços no 2-2-2, conduzindo a bola e ligando o meio-campo ao ataque.",
        "atributos": "Passe, Drible, Técnica, Primeiro Toque, Visão de Jogo, Aceleração",
        "needs": {"passe": 4, "drible": 4, "tecnica": 4, "primeiro_toque": 4, "visao": 4, "aceleracao": 4, "sem_bola": 3, "trabalho": 3},
        "advance": 0.095, "def_advance": 0.0, "width": 0.040,
        "pass_w": 1.18, "dribble_w": 1.28, "shot_w": 1.20, "cross_w": 1.15,
        "through_bias": 0.10, "receive_pass_w": 1.25, "receive_through_w": 1.28, "receive_cross_w": 1.05,
        "intercept_bonus": 0.03, "duel_bonus": 1.5,
    },
    "mix_equilibrador": {
        "id": "mix_equilibrador",
        "nome": "Pivô Equilibrador",
        "curto": "Equilibrador",
        "desc": "Fecha o corredor central e protege os centrais no 2-2-2, garantindo equilíbrio e recuperação.",
        "atributos": "Posicionamento, Desarme, Antecipação, Índice de Trabalho, Resistência, Passe",
        "needs": {"posicionamento": 5, "desarme": 5, "antecipacao": 4, "trabalho": 4, "resistencia": 4, "passe": 4, "decisoes": 3, "marcacao": 3},
        "advance": 0.040, "def_advance": -0.030, "width": -0.025,
        "pass_w": 1.28, "dribble_w": 0.82, "shot_w": 0.80, "cross_w": 0.80,
        "through_bias": 0.04, "receive_pass_w": 1.15, "receive_through_w": 0.82, "receive_cross_w": 0.85,
        "intercept_bonus": 0.10, "duel_bonus": 3.4,
    },
    "mix_ala_criativo": {
        "id": "mix_ala_criativo",
        "nome": "Médio Aberto Criativo",
        "curto": "Médio Aberto",
        "desc": "Abre na faixa lateral para dar largura ao 2-2-2, encarar no 1x1 e cruzar para a dupla da frente.",
        "atributos": "Cruzamento, Drible, Velocidade, Aceleração, Técnica, Visão de Jogo",
        "needs": {"cruzamento": 5, "drible": 4, "velocidade": 4, "aceleracao": 4, "tecnica": 4, "visao": 3, "passe": 3, "sem_bola": 3},
        "advance": 0.110, "def_advance": 0.005, "width": 0.085,
        "pass_w": 1.0, "dribble_w": 1.35, "shot_w": 1.05, "cross_w": 1.65,
        "through_bias": 0.06, "receive_pass_w": 1.18, "receive_through_w": 1.32, "receive_cross_w": 1.0,
        "intercept_bonus": 0.01, "duel_bonus": 1.2,
    },

    # ---------- AVANÇADOS (A / AW) ----------
    "av_finalizador": {
        "id": "av_finalizador",
        "nome": "Ponta de Lança Fixo (Finalizador)",
        "curto": "Finalizador",
        "desc": "Fica na zona de finalização: letal ao primeiro toque, no jogo aéreo e dentro da área.",
        "atributos": "Finalização, Compostura, Cabeceamento, Primeiro Toque, Sem Bola, Força",
        "needs": {"finalizacao": 6, "compostura": 5, "cabecemento": 4, "primeiro_toque": 4, "sem_bola": 4, "forca": 3, "impulsao": 3},
        "advance": 0.130, "def_advance": 0.010, "width": -0.035,
        "pass_w": 0.82, "dribble_w": 0.95, "shot_w": 1.65, "cross_w": 0.70,
        "through_bias": 0.0, "receive_pass_w": 1.08, "receive_through_w": 1.30, "receive_cross_w": 1.60,
        "intercept_bonus": 0.0, "duel_bonus": 1.8,
    },
    "av_movel": {
        "id": "av_movel",
        "nome": "Avançado Móvel (Rutura)",
        "curto": "Av. Móvel",
        "desc": "Ataca constantemente a profundidade nas costas da defesa em velocidade.",
        "atributos": "Velocidade, Aceleração, Sem Bola, Finalização, Drible, Compostura",
        "needs": {"velocidade": 5, "aceleracao": 5, "sem_bola": 5, "finalizacao": 4, "drible": 4, "compostura": 4, "primeiro_toque": 3},
        "advance": 0.145, "def_advance": 0.015, "width": 0.025,
        "pass_w": 0.90, "dribble_w": 1.35, "shot_w": 1.42, "cross_w": 0.95,
        "through_bias": 0.04, "receive_pass_w": 1.10, "receive_through_w": 1.65, "receive_cross_w": 1.25,
        "intercept_bonus": 0.02, "duel_bonus": 1.2,
    },
    "av_falso9": {
        "id": "av_falso9",
        "nome": "Falso 9 (Segundo Avançado)",
        "curto": "Falso 9",
        "desc": "Recua para entrelinhas para ligar o jogo, arrastar defesas e isolar os colegas.",
        "atributos": "Passe, Visão de Jogo, Técnica, Drible, Primeiro Toque, Decisões, Finalização",
        "needs": {"passe": 5, "visao": 5, "tecnica": 5, "drible": 4, "primeiro_toque": 4, "decisoes": 4, "compostura": 4, "finalizacao": 3},
        "advance": 0.065, "def_advance": -0.010, "width": -0.020,
        "pass_w": 1.38, "dribble_w": 1.25, "shot_w": 1.15, "cross_w": 0.90,
        "through_bias": 0.18, "receive_pass_w": 1.36, "receive_through_w": 1.10, "receive_cross_w": 0.92,
        "intercept_bonus": 0.03, "duel_bonus": 1.2,
    },
    "av_extremo_ataque": {
        "id": "av_extremo_ataque",
        "nome": "Avançado Interior / Extremo",
        "curto": "Av. Interior",
        "desc": "Cai nas faixas para encarar no 1x1, tirar cruzamentos ou fletir para rematar.",
        "atributos": "Drible, Aceleração, Velocidade, Técnica, Finalização, Cruzamento",
        "needs": {"drible": 5, "aceleracao": 5, "velocidade": 4, "tecnica": 4, "finalizacao": 4, "cruzamento": 4, "agilidade": 4},
        "advance": 0.120, "def_advance": 0.0, "width": 0.080,
        "pass_w": 0.95, "dribble_w": 1.48, "shot_w": 1.32, "cross_w": 1.45,
        "through_bias": 0.06, "receive_pass_w": 1.15, "receive_through_w": 1.42, "receive_cross_w": 1.18,
        "intercept_bonus": 0.01, "duel_bonus": 1.0,
    },
}

ROLE_OPTIONS_BY_POSITION = {
    "GR": ["gr_classico", "gr_libero"],
    "D":  ["dc_destruidor", "dc_construtor", "dc_cobertura"],
    "DC": ["dc_destruidor", "dc_construtor", "dc_cobertura"],
    "DL": ["dl_ala_completo", "dl_defensivo", "dl_invertido", "dl_ofensivo"],
    "MC": ["mc_organizador", "mc_trinco", "mc_box_to_box", "mc_ofensivo"],
    "ML": ["ml_extremo_puro", "ml_extremo_invertido", "ml_ala_equilibrado", "ml_criativo_interior"],
    "MIX": ["mix_interior", "mix_equilibrador", "mix_ala_criativo", "mc_box_to_box"],
    "A":  ["av_finalizador", "av_movel", "av_falso9", "av_extremo_ataque"],
    "AW": ["av_movel", "av_finalizador", "av_falso9", "av_extremo_ataque"],
}

ROLE_CATALOG = {
    k: {
        "id": v["id"],
        "nome": v["nome"],
        "curto": v["curto"],
        "desc": v["desc"],
        "atributos": v["atributos"],
    }
    for k, v in ROLE_DEFINITIONS.items()
}


def validar_funcoes(tatica, funcoes=None, position_layout=None):
    """Garante uma lista de 7 funções válidas para a tática escolhida."""
    layout = (position_layout or POSITION_LAYOUT)[tatica]
    out = []
    for i, pos in enumerate(layout):
        opcoes = ROLE_OPTIONS_BY_POSITION.get(pos, ["mc_organizador"])
        escolha = funcoes[i] if isinstance(funcoes, list) and i < len(funcoes) else None
        out.append(escolha if escolha in opcoes else opcoes[0])
    return out


class FootballManagerEngine:
    MIN = 60
    TICKS = 4
    FIELD_X = 105.0
    FIELD_Y = 68.0
    ACTION_SECONDS = 15.0
    PRESSURE_LEVEL = 0.56
    TEMPO_LEVEL = 0

    def __init__(self, name_a, name_b, players_a, players_b, tactic_a, tactic_b, coordinates, position_layout=None, roles_a=None, roles_b=None):
        self.names = [name_a, name_b]
        self.teams = [players_a, players_b]
        self.tactics = [tactic_a, tactic_b]
        self.coordinates = coordinates
        position_layout = position_layout or POSITION_LAYOUT
        self.positions = [position_layout[tactic_a], position_layout[tactic_b]]
        self.roles = [
            validar_funcoes(tactic_a, roles_a, position_layout),
            validar_funcoes(tactic_b, roles_b, position_layout),
        ]
        self.base = [coordinates[self.tactics[k]] for k in range(2)]
        self.ev = []
        self.pos = random.randint(0, 1)
        self.players = [[{"x": 0.5, "y": 0.5, "ativo": True} for _ in range(7)] for _ in range(2)]
        self.fadiga = [[0.0] * 7 for _ in range(2)]
        self.last_pass = [None, None]
        self.stats = [self._team_stats(), self._team_stats()]
        self.pstats = [[self._player_stats(k, i) for i in range(7)] for k in range(2)]
        self.markers = [[], []]
        self.ball = {"x": 0.5, "y": 0.5, "z": 0.0, "vx": 0.0, "vy": 0.0, "vz": 0.0, "owner": None}
        self.c = 1
        self.z = 1
        for team in range(2):
            for i, (u, v) in enumerate(self.base[team]):
                x, y = self._world(team, u, v)
                self.players[team][i].update(x=x, y=y)
        self.c = self._kickoff_player(self.pos)
        self._owner(self.pos, self.c)

    def _role(self, team, index):
        role_id = self.roles[team][index]
        return ROLE_DEFINITIONS.get(role_id, ROLE_DEFINITIONS["mc_organizador"])

    @staticmethod
    def _team_stats():
        return dict(golos=0, posse=0, rem=0, bal=0, def_=0, pc=0, pt=0, des=0, inte=0,
                    faltas=0, amarelos=0, vermelhos=0, impedimentos=0, cantos=0,
                    penaltis=0, lesoes=0, duelos=0, cruzamentos=0, perdas=0)

    def _player_stats(self, team, index):
        p = self.teams[team][index]
        role = self._role(team, index)
        return dict(nome=p.nome, pos="GR" if index == 0 else "/".join(p.pos),
                    posicao=self.positions[team][index], funcao=role["curto"], funcao_nome=role["nome"],
                    golos=0, ast=0, rem=0, bal=0, pc=0, pt=0,
                    dri=0, des=0, inte=0, bloq=0, def_=0, gs=0, faltas=0, amarelos=0,
                    vermelhos=0, lesao=0, perdas=0, recuperacoes=0, nota=6.0, resumo="")

    @staticmethod
    def _clamp(value, low, high):
        return max(low, min(high, value))

    @staticmethod
    def _safe(value, fallback=50.0):
        try:
            value = float(value)
            return value if math.isfinite(value) else fallback
        except (TypeError, ValueError):
            return fallback

    def _attr(self, team, index, key):
        p = self.teams[team][index]
        raw = self._safe(p.a.get(key, 50.0))
        position = self.positions[team][index]
        role = self._role(team, index)
        if position == "MIX":
            need = {k: (POSITION_NEEDS["MC"].get(k, 0) + POSITION_NEEDS["ML"].get(k, 0)) / 2 for k in ALL_ATTRIBUTES}
        else:
            need = dict(POSITION_NEEDS[position])
        if position == "GR":
            weights = {k: 0.45 for k in OUTFIELD_ATTRIBUTES}
            weights.update({k: 1.0 for k in GOALKEEPER_ATTRIBUTES})
        else:
            weights = {k: 1.0 for k in OUTFIELD_ATTRIBUTES}
            weights.update({k: 0.25 for k in GOALKEEPER_ATTRIBUTES})
        for attr, priority in need.items():
            weights[attr] += priority * 0.75
        role_needs = role.get("needs", {})
        for attr, priority in role_needs.items():
            weights[attr] = weights.get(attr, 1.0) + priority * 1.35
        profile = sum(self._safe(p.a.get(attr, 50.0)) * weight for attr, weight in weights.items()) / sum(weights.values())
        role_focus = role_needs.get(key, 0)
        # Se o atributo pedido é prioritário para a função escolhida, o perfil funcional pesa mais
        effective = raw * (0.68 if role_focus >= 4 else 0.74) + profile * (0.32 if role_focus >= 4 else 0.26)
        return effective * (1 - self.fadiga[team][index] * 0.30)

    def _foot_penalty(self, team, index, y):
        p = self.teams[team][index]
        foot = str(p.a.get("pe_preferido", "Direito")).casefold()
        local_y = y if team == 0 else 1 - y
        weak_side = (local_y < 0.5 and "direito" in foot) or (local_y >= 0.5 and "esquerdo" in foot)
        weak_foot = self._safe(p.a.get("pe_fraco", 3.0), 3.0)
        return max(0.0, 5.0 - weak_foot) * 1.4 if weak_side else 0.0

    def _world(self, team, u, v):
        return (u, v) if team == 0 else (1 - u, 1 - v)

    def _local(self, team, x, y):
        return (x, y) if team == 0 else (1 - x, 1 - y)

    def _local_ball(self, team):
        return self._local(team, self.ball["x"], self.ball["y"])

    def _u(self, team, x):
        return x if team == 0 else 1 - x

    def _kickoff_player(self, team):
        candidates = [i for i in range(1, 7) if self._active(team, i)]
        return max(candidates, key=lambda i: self._attr(team, i, "decisoes")) if candidates else 0

    def _active(self, team, index):
        return self.players[team][index]["ativo"]

    def _keeper(self, team):
        if self._active(team, 0):
            return 0
        available = [i for i in range(1, 7) if self._active(team, i)]
        return max(available, key=lambda i: self._attr(team, i, "reflexos")) if available else 0

    def _owner(self, team, index, x=None, y=None):
        self.pos, self.c = team, index
        self.ball["owner"] = (team, index)
        if x is None or y is None:
            x, y = self.players[team][index]["x"], self.players[team][index]["y"]
        self.ball.update(x=x, y=y, z=0.0, vx=0.0, vy=0.0, vz=0.0)

    def _distance(self, a, b):
        dx = (a["x"] - b["x"]) * self.FIELD_X
        dy = (a["y"] - b["y"]) * self.FIELD_Y
        return math.hypot(dx, dy)

    def _speed(self, team, index, sprint=True):
        pace = self._attr(team, index, "velocidade")
        acc = self._attr(team, index, "aceleracao")
        work = self._attr(team, index, "trabalho")
        base = 4.0 + pace * 0.021 + acc * 0.009
        if sprint:
            base += 0.65
        return max(2.7, base * (1 - self.fadiga[team][index] * (0.28 if work >= 70 else 0.42)))

    def _pressure(self, team, index):
        p = self.players[team][index]
        opp = 1 - team
        nearest = min((self._distance(p, q) for q in self.players[opp] if q["ativo"]), default=35.0)
        return max(0.0, (13.0 - nearest) / 13.0) * self.PRESSURE_LEVEL * 26.0

    def _move_players(self):
        for team in range(2):
            attacking = team == self.pos
            ball_u, ball_v = self._local_ball(team)
            for i, p in enumerate(self.players[team]):
                if not p["ativo"]:
                    continue
                base_u, base_v = self.base[team][i]
                position = self.positions[team][i]
                role = self._role(team, i)
                advance = role.get("advance", 0.06)
                def_advance = role.get("def_advance", 0.0)
                width_shift = role.get("width", 0.0)
                target_u = base_u + (advance if attacking else def_advance)
                target_v = base_v
                if attacking:
                    target_u += (ball_u - 0.5) * (0.20 if i else 0.04)
                    target_v += (ball_v - base_v) * (0.24 if position in MIDFIELD_POSITIONS | FORWARD_POSITIONS else 0.14)
                    if abs(base_v - 0.5) > 0.04:
                        # width_shift > 0 aproxima da linha lateral; width_shift < 0 flete para o corredor central
                        side_sign = -1.0 if base_v < 0.5 else 1.0
                        target_v += side_sign * width_shift
                else:
                    target_u += (ball_u - 0.48) * (0.22 if position in DEFENDER_POSITIONS else 0.12)
                    target_v += (ball_v - base_v) * 0.22
                    if abs(base_v - 0.5) > 0.04:
                        side_sign = -1.0 if base_v < 0.5 else 1.0
                        target_v += side_sign * (width_shift * 0.45)
                target_u = self._clamp(target_u, 0.04, 0.96)
                target_v = self._clamp(target_v, 0.045, 0.955)
                wx, wy = self._world(team, target_u, target_v)
                dist = self._distance(p, {"x": wx, "y": wy})
                limit = self._speed(team, i) * self.ACTION_SECONDS * 0.10
                ratio = min(1.0, limit / max(dist, 0.01))
                p["x"] += (wx - p["x"]) * ratio
                p["y"] += (wy - p["y"]) * ratio
        if self.ball["owner"]:
            team, index = self.ball["owner"]
            if self._active(team, index):
                self.ball["x"], self.ball["y"], self.ball["z"] = self.players[team][index]["x"], self.players[team][index]["y"], 0.0

    def _event(self, minute, kind, text, team=None, carrier=None, receiver=None, defender=None,
               start=None, end=None, winner=None, goal=False):
        team = self.pos if team is None else team
        carrier = self.c if carrier is None else carrier
        if 0 <= carrier < 7:
            progress = self._u(team, self.players[team][carrier]["x"])
            self.z = 0 if progress < 0.34 else 1 if progress < 0.68 else 2
        start = start or {"x": self.ball["x"], "y": self.ball["y"], "z": self.ball["z"]}
        end = end or start
        self.ev.append({
            "m": minute, "tipo": kind, "txt": text, "eq": team, "c": carrier,
            "a": receiver, "d": defender, "z": self.z, "golo": goal,
            "placar": [self.stats[0]["golos"], self.stats[1]["golos"]],
            "ball": {"from": start, "to": end}, "winner": winner,
            "jogadores": [[{"x": round(player["x"], 5), "y": round(player["y"], 5),
                            "ativo": bool(player["ativo"])} for player in side]
                           for side in self.players],
        })

    def _prob(self, value):
        return self._clamp(value, 0.02, 0.98)

    def _nearest_defender(self, team, index):
        carrier = self.players[team][index]
        ids = [i for i in range(7) if self._active(1 - team, i)]
        return min(ids, key=lambda i: self._distance(carrier, self.players[1 - team][i])) if ids else self._keeper(1 - team)

    def _race(self, target, preferred=None):
        arrivals = []
        for team in range(2):
            for index, p in enumerate(self.players[team]):
                if not p["ativo"]:
                    continue
                dist = self._distance(p, target)
                anticipate = self._attr(team, index, "antecipacao")
                role = self._role(team, index)
                reaction = 0.42 - anticipate * 0.002 - role.get("intercept_bonus", 0.0) * 0.35
                if preferred == (team, index):
                    reaction -= 0.14
                if target.get("z", 0.0) >= 3.0:
                    height = self._safe(self.teams[team][index].a.get("altura", 1.75), 1.75)
                    aerial = 0.55 * self._attr(team, index, "cabecemento") + 0.30 * self._attr(team, index, "impulsao") + 0.15 * min(100, height * 52)
                    reaction -= aerial / 420
                arrivals.append((dist / self._speed(team, index) + max(0.06, reaction), team, index))
        return min(arrivals) if arrivals else (99.0, self.pos, self.c)

    def _segment_interceptor(self, team, start, end, flight_time):
        dx, dy = (end["x"] - start["x"]) * self.FIELD_X, (end["y"] - start["y"]) * self.FIELD_Y
        length2 = dx * dx + dy * dy
        best = None
        for index, p in enumerate(self.players[1 - team]):
            if not p["ativo"]:
                continue
            px, py = (p["x"] - start["x"]) * self.FIELD_X, (p["y"] - start["y"]) * self.FIELD_Y
            frac = 0.0 if length2 == 0 else self._clamp((px * dx + py * dy) / length2, 0.0, 1.0)
            spot = {"x": start["x"] + (end["x"] - start["x"]) * frac,
                    "y": start["y"] + (end["y"] - start["y"]) * frac}
            gap = self._distance(p, spot)
            role = self._role(1 - team, index)
            bonus = role.get("intercept_bonus", 0.0)
            reach_time = gap / self._speed(1 - team, index) + 0.36 - self._attr(1 - team, index, "antecipacao") * 0.002 - bonus
            at_ball_time = max(0.0, flight_time * frac)
            if gap < 2.8 + bonus * 2.5 and reach_time <= at_ball_time + 0.20 + bonus * 0.5:
                score = reach_time + gap * 0.015
                if best is None or score < best[0]:
                    best = (score, index, spot)
        return best

    def _offside_line(self, defending_team, minute):
        defenders = [i for i in range(7) if self._active(defending_team, i) and self.positions[defending_team][i] in DEFENDER_POSITIONS]
        if not defenders:
            return 0.24
        line = sorted((self._u(defending_team, self.players[defending_team][i]["x"]) for i in defenders), reverse=True)
        base_line = line[min(1, len(line) - 1)]
        group_skill = sum((self._attr(defending_team, i, "decisoes") + self._attr(defending_team, i, "antecipacao")) / 2 for i in defenders) / len(defenders)
        cover_count = sum(1 for i in defenders if self.roles[defending_team][i] == "dc_cobertura")
        chance = self._clamp(0.18 + group_skill / 100 * 0.58 + cover_count * 0.05, 0.28, 0.82)
        if random.random() < chance:
            base_line += 0.035
        return base_line

    def _is_offside(self, team, receiver, ball_u):
        u = self._u(team, self.players[team][receiver]["x"])
        line = self._offside_line(1 - team, 0)
        return ball_u > 0.48 and u > max(line, ball_u) + 0.015

    def _flight_time(self, start, end, team, passer, loft=0):
        distance = self._distance(start, end)
        if self.positions[team][passer] == "GR":
            pass_skill = max(self._attr(team, passer, "pontape_baliza"), self._attr(team, passer, "lancamento"))
        else:
            pass_skill = self._attr(team, passer, "passe")
        speed = self._clamp(19.0 + pass_skill * 0.16 - loft * 0.25, 18.0, 34.0)
        return max(0.20, distance / speed)

    def _choose_receiver(self, team, carrier, through=False, cross=False):
        source_u = self._u(team, self.players[team][carrier]["x"])
        ids, weights = [], []
        for i in range(1, 7):
            if i == carrier or not self._active(team, i):
                continue
            p = self.players[team][i]
            u = self._u(team, p["x"])
            position = self.positions[team][i]
            role = self._role(team, i)
            weight = 1.0 + self._attr(team, i, "visao") / 60 + self._attr(team, i, "decisoes") / 100
            if through:
                weight *= (0.55 + max(0.0, u - source_u) * 3.5 + self._attr(team, i, "sem_bola") / 120) * role.get("receive_through_w", 1.0)
            else:
                weight *= (1.0 + max(-0.12, min(0.12, u - source_u))) * role.get("receive_pass_w", 1.0)
            if position == "MC":
                weight *= 1.15
            elif position in {"ML", "MIX", "DL"} and abs(p["y"] - 0.5) > 0.18:
                weight *= 1.12
            if cross:
                weight *= (1.55 if position in FORWARD_POSITIONS else 0.82) * role.get("receive_cross_w", 1.0)
                height = self._safe(self.teams[team][i].a.get("altura", 1.75), 1.75)
                aerial = 0.52 * self._attr(team, i, "cabecemento") + 0.30 * self._attr(team, i, "impulsao") + 0.18 * min(100, height * 52)
                weight *= 0.58 + aerial / 100
            ids.append(i)
            weights.append(max(0.08, weight))
        return random.choices(ids, weights)[0] if ids else self._keeper(team)

    def _pass(self, minute, through=False, cross=False, set_piece=False):
        team, carrier = self.pos, self.c
        receiver = self._choose_receiver(team, carrier, through, cross)
        passer_p = self.teams[team][carrier]
        target_player = self.players[team][receiver]
        receiver_role = self._role(team, receiver)
        start = {"x": self.ball["x"], "y": self.ball["y"], "z": self.ball["z"]}
        receiver_u = self._u(team, target_player["x"])
        receiver_v = target_player["y"] if team == 0 else 1 - target_player["y"]
        if through:
            run_boost = 0.055 if receiver_role["id"] in {"av_movel", "ml_extremo_invertido", "dl_ofensivo"} else 0.045
            receiver_u += run_boost + self._attr(team, receiver, "velocidade") / 1800
        elif cross:
            receiver_u = max(receiver_u, 0.84)
        receiver_u = self._clamp(receiver_u, 0.04, 0.97)
        receiver_v = self._clamp(receiver_v, 0.06, 0.94)
        tx, ty = self._world(team, receiver_u, receiver_v)
        passing = self._attr(team, carrier, "passe")
        if self.positions[team][carrier] == "GR":
            passing = max(self._attr(team, carrier, "pontape_baliza"), self._attr(team, carrier, "lancamento"))
        accuracy = 0.38 * passing + 0.18 * self._attr(team, carrier, "tecnica") + 0.18 * self._attr(team, carrier, "decisoes") + 0.14 * self._attr(team, carrier, "visao") + 0.12 * self._attr(team, receiver, "primeiro_toque")
        if cross:
            accuracy = 0.46 * self._attr(team, carrier, "cruzamento") + 0.24 * passing + 0.18 * self._attr(team, carrier, "tecnica") + 0.12 * self._attr(team, receiver, "primeiro_toque")
        accuracy -= self._foot_penalty(team, carrier, self.ball["y"])
        error_m = max(1.2, (105 - accuracy) * 0.11 + (0.7 if through else 0.0))
        err_x = random.gauss(0, error_m) / self.FIELD_X
        err_y = random.gauss(0, error_m * 0.75) / self.FIELD_Y
        end = {"x": self._clamp(tx + err_x * (1 if team == 0 else -1), 0.025, 0.975),
               "y": self._clamp(ty + err_y * (1 if team == 0 else -1), 0.035, 0.965),
               "z": 7.5 if cross or (through and random.random() < 0.18) else (2.0 if random.random() < 0.10 else 0.3)}
        if (through or receiver_u > self._u(team, start["x"]) + 0.025) and self._is_offside(team, receiver, self._u(team, start["x"])):
            self.stats[team]["impedimentos"] += 1
            self.stats[team]["perdas"] += 1
            self.stats[team]["pt"] += 1
            self.pstats[team][carrier]["pt"] += 1
            self.pstats[team][carrier]["perdas"] += 1
            self._event(minute, "fora_de_jogo", f"Fora de jogo de {self.teams[team][receiver].nome}; a linha defensiva subiu em bloco.", team, carrier, receiver, None, start, end)
            self._owner(1 - team, self._keeper(1 - team))
            return
        flight = self._flight_time(start, end, team, carrier, end["z"])
        self.ball.update(x=start["x"], y=start["y"], z=start["z"],
                         vx=(end["x"] - start["x"]) / flight, vy=(end["y"] - start["y"]) / flight,
                         vz=(end["z"] - start["z"]) / flight, owner=None)
        interceptor = self._segment_interceptor(team, start, end, flight)
        if interceptor:
            _, defender, spot = interceptor
            self.stats[1 - team]["inte"] += 1
            self.pstats[1 - team][defender]["inte"] += 1
            self.pstats[1 - team][defender]["recuperacoes"] += 1
            self.stats[team]["pt"] += 1
            self.pstats[team][carrier]["pt"] += 1
            self._event(minute, "intercepta", f"{self.teams[1-team][defender].nome} corta a trajetória do passe de {passer_p.nome}.", team, carrier, None, defender, start, {"x": spot["x"], "y": spot["y"], "z": 0}, (1-team, defender))
            self._owner(1 - team, defender, spot["x"], spot["y"])
            return
        preferred = (team, receiver)
        arrival, winner_team, winner_index = self._race({"x": end["x"], "y": end["y"], "z": end["z"]}, preferred)
        error_distance = self._distance({"x": tx, "y": ty}, end)
        if winner_team == team and winner_index == receiver and arrival <= flight + 1.15 and error_distance < (8.0 if cross else 7.0):
            self.stats[team]["pt"] += 1
            self.stats[team]["pc"] += 1
            self.pstats[team][carrier]["pt"] += 1
            self.pstats[team][carrier]["pc"] += 1
            self.pstats[team][receiver]["pc"] += 1
            self.last_pass[team] = (minute, carrier, receiver)
            kind = "canto" if cross and set_piece else "passe"
            label = "cruza" if cross else ("mete a bola nas costas da defesa para" if through else "joga para")
            self._event(minute, kind, f"{passer_p.nome} {label} {self.teams[team][receiver].nome}.", team, carrier, receiver, None, start, end, (team, receiver))
            self._owner(team, receiver, end["x"], end["y"])
            return
        if winner_team == team:
            self.stats[team]["pt"] += 1
            self.pstats[team][carrier]["pt"] += 1
            self.pstats[team][carrier]["perdas"] += 1
            self.stats[team]["perdas"] += 1
            self._event(minute, "bola_livre", f"Passe de {passer_p.nome} sai da medida; a bola fica solta no espaço.", team, carrier, receiver, None, start, end, (team, winner_index))
            self._owner(team, winner_index, end["x"], end["y"])
            self.pstats[team][winner_index]["recuperacoes"] += 1
        else:
            self.stats[team]["pt"] += 1
            self.pstats[team][carrier]["pt"] += 1
            self.pstats[team][carrier]["perdas"] += 1
            self.stats[team]["perdas"] = self.stats[team].get("perdas", 0) + 1
            self.stats[1-team]["inte"] += 1
            self.pstats[1-team][winner_index]["inte"] += 1
            self.pstats[1-team][winner_index]["recuperacoes"] += 1
            self._event(minute, "bola_livre", f"Bola no espaço: {self.teams[team][receiver].nome} e {self.teams[1-team][winner_index].nome} arrancam para a disputa.", team, carrier, receiver, winner_index, start, end, (1-team, winner_index))
            self._owner(1-team, winner_index, end["x"], end["y"])

    def _tick(self, minute):
        self._move_players()
        for team in range(2):
            for i in range(7):
                if not self._active(team, i):
                    continue
                effort = 0.22 + self.PRESSURE_LEVEL * 0.20
                stamina = self._attr(team, i, "resistencia")
                self.fadiga[team][i] = min(0.72, self.fadiga[team][i] + (self.ACTION_SECONDS / 3600) * max(0.04, effort - stamina / 420))
        self.stats[self.pos]["posse"] += 1
        p = self.teams[self.pos][self.c]
        P = self.pstats[self.pos][self.c]
        role = self._role(self.pos, self.c)
        if self.c == self._keeper(self.pos):
            self._pass(minute, through=random.random() < max(0.0, role.get("through_bias", 0.0)))
            return
        team, carrier = self.pos, self.c
        u = self._u(team, self.players[team][carrier]["x"])
        pressure = self._pressure(team, carrier)
        position = self.positions[team][carrier]
        can_shoot = u > (0.50 if role["id"] in {"ml_extremo_invertido", "mc_ofensivo", "mc_box_to_box"} else 0.54)
        wide_role = role["id"] in {"dl_ala_completo", "dl_ofensivo", "ml_extremo_puro", "ml_ala_equilibrado", "mix_ala_criativo", "av_extremo_ataque"}
        can_cross = u > (0.55 if wide_role else 0.59) and (abs(self.players[team][carrier]["y"] - 0.5) > 0.17 or wide_role) and (position in {"DL", "ML", "AW", "MIX"} or wide_role)
        weights = [
            30.0 * role.get("pass_w", 1.0),
            20.0 * role.get("dribble_w", 1.0),
            (max(2.0, 14 + (u - 0.54) * 62) if can_shoot else 2.0) * role.get("shot_w", 1.0),
            (10.0 if can_cross else 1.0) * role.get("cross_w", 1.0),
        ]
        traits = str(p.a.get("traits", "")).casefold()
        if "finta frequentemente" in traits:
            weights[1] *= 1.35
        action = random.choices(("pass", "dribble", "shot", "cross"), weights)[0]
        defender = self._nearest_defender(team, carrier)
        if action == "pass":
            through_chance = 0.12 + self._attr(team, carrier, "visao") / 500 + role.get("through_bias", 0.0)
            trait = str(p.a.get("traits", "")).casefold()
            self._pass(minute, through=random.random() < self._clamp(through_chance, 0.04, 0.58) or "passes de rutura" in trait)
        elif action == "cross":
            self.stats[team]["cruzamentos"] += 1
            self._pass(minute, cross=True)
        elif action == "dribble":
            d = self.teams[1-team][defender]
            def_role = self._role(1-team, defender)
            attack = 0.38 * self._attr(team, carrier, "drible") + 0.24 * self._attr(team, carrier, "tecnica") + 0.22 * self._attr(team, carrier, "aceleracao") + 0.16 * self._attr(team, carrier, "velocidade")
            defend = 0.30 * self._attr(1-team, defender, "desarme") + 0.20 * self._attr(1-team, defender, "marcacao") + 0.21 * self._attr(1-team, defender, "antecipacao") + 0.15 * self._attr(1-team, defender, "agilidade") + 0.14 * self._attr(1-team, defender, "forca")
            attack += 3.0 if role.get("dribble_w", 1.0) >= 1.25 else 0.0
            defend += def_role.get("duel_bonus", 0.0)
            pressure_mod = self.PRESSURE_LEVEL
            win = random.random() < self._prob(0.49 + (attack - defend) / 115 - pressure_mod * pressure / 110)
            self.stats[team]["duelos"] += 1
            self.stats[1-team]["duelos"] += 1
            if win:
                P["dri"] += 1
                self._event(minute, "drible", f"{p.nome} ultrapassa {d.nome} com um drible.", team, carrier, None, defender)
                local_u, local_v = self._local(team, self.players[team][carrier]["x"], self.players[team][carrier]["y"])
                local_u = min(0.97, local_u + 0.038)
                if role["id"] in {"ml_extremo_invertido", "dl_invertido", "av_extremo_ataque"}:
                    local_v += (0.5 - local_v) * 0.18
                x, y = self._world(team, local_u, local_v)
                self._owner(team, carrier, x, y)
            else:
                foul_chance = 0.045 + self._attr(1-team, defender, "agressividade") / 680 + pressure_mod * 0.055
                if def_role["id"] in {"dc_destruidor", "mc_trinco", "dl_defensivo"}:
                    foul_chance += 0.015
                if random.random() < foul_chance:
                    self._foul(minute, team, carrier, defender)
                else:
                    self.stats[1-team]["des"] += 1
                    self.pstats[1-team][defender]["des"] += 1
                    self.pstats[1-team][defender]["recuperacoes"] += 1
                    self.stats[team]["perdas"] += 1
                    self._event(minute, "desarme", f"{d.nome} desarma {p.nome}.", team, carrier, None, defender)
                    self._owner(1-team, defender)
        else:
            self._shot(minute)

    def _shot(self, minute, penalty=False, set_piece=False, taker=None, label="remate"):
        team = self.pos
        shooter = self.c if taker is None else taker
        shot_player = self.teams[team][shooter]
        player = self.players[team][shooter]
        role = self._role(team, shooter)
        u = self._u(team, player["x"])
        y = player["y"] if team == 0 else 1 - player["y"]
        distance = 11.0 if penalty else max(4.0, (1 - u) * self.FIELD_X)
        angle_penalty = abs(y - 0.5) * (21 if role["id"] in {"ml_extremo_invertido", "av_extremo_ataque"} else 28)
        defender = self._nearest_defender(team, shooter)
        gk = self._keeper(1-team)
        pressure = self._pressure(team, shooter)
        fin = self._attr(team, shooter, "finalizacao")
        tech = self._attr(team, shooter, "tecnica")
        composure = self._attr(team, shooter, "compostura")
        skill = 0.43 * fin + 0.21 * tech + 0.17 * composure + 0.11 * self._attr(team, shooter, "decisoes") + 0.08 * self._attr(team, shooter, "primeiro_toque")
        if role["id"] == "av_finalizador":
            skill += 2.2
        elif role["id"] in {"ml_extremo_invertido", "mc_ofensivo"}:
            skill += 1.5
        if set_piece:
            skill = 0.52 * self._attr(team, shooter, "bola_parada") + 0.28 * tech + 0.20 * fin
        if penalty:
            skill = 0.48 * fin + 0.34 * composure + 0.18 * self._attr(team, shooter, "bola_parada")
        quality = skill - distance * (0.26 if not penalty else 0.05) - angle_penalty - pressure * 0.12
        quality -= self._foot_penalty(team, shooter, player["y"])
        traits = str(shot_player.a.get("traits", "")).casefold()
        if "remata com força" in traits:
            quality += 2.5
        if "remata em jeito" in traits:
            quality += 2.0
        if penalty:
            quality += 28
        on_target_chance = self._clamp(0.46 + (quality - 20) / 110, 0.30, 0.98)
        gk_skill = (0.36 * self._attr(1-team, gk, "reflexos") + 0.20 * self._attr(1-team, gk, "um_para_um")
                    + 0.14 * self._attr(1-team, gk, "posicionamento") + 0.12 * self._attr(1-team, gk, "decisoes")
                    + 0.10 * self._attr(1-team, gk, "comando_area") + 0.08 * self._attr(1-team, gk, "jogo_aereo"))
        if penalty:
            goal_chance = self._clamp(0.79 + (skill - gk_skill) / 160, 0.66, 0.91)
            on_target_chance = 0.96
        else:
            goal_chance = self._clamp(0.40 + (quality - gk_skill) / 52, 0.08, 0.82)
        on_target = random.random() < on_target_chance
        scored = on_target and random.random() < goal_chance
        start = {"x": self.ball["x"], "y": self.ball["y"], "z": 0.0}
        goal_y = self._clamp(0.5 + random.gauss(0, 0.12 + distance / 160), 0.12, 0.88)
        gx, gy = self._world(team, 1.0, goal_y)
        if not on_target:
            gx, gy = self._world(team, 1.0, self._clamp(goal_y + random.choice((-1, 1)) * random.uniform(0.10, 0.34), 0.02, 0.98))
        end = {"x": gx, "y": gy, "z": random.uniform(0.1, 1.8)}
        flight = self._flight_time(start, end, team, shooter, end["z"])
        self.ball.update(x=start["x"], y=start["y"], z=start["z"],
                         vx=(end["x"] - start["x"]) / flight, vy=(end["y"] - start["y"]) / flight,
                         vz=(end["z"] - start["z"]) / flight, owner=None)
        S = self.stats[team]
        P = self.pstats[team][shooter]
        S["rem"] += 1
        P["rem"] += 1
        if penalty:
            S["penaltis"] += 1
        if on_target:
            S["bal"] += 1
            P["bal"] += 1
        if scored:
            S["golos"] += 1
            P["golos"] += 1
            self.pstats[1-team][gk]["gs"] += 1
            ast = None
            last = self.last_pass[team]
            if last and last[0] >= minute - 1 and last[2] == shooter and last[1] != shooter:
                self.pstats[team][last[1]]["ast"] += 1
                ast = self.teams[team][last[1]].nome
            self.markers[team].append(dict(nome=shot_player.nome, m=minute, ast=ast))
            self._event(minute, "golo", f"GOLO! {shot_player.nome} marca{' de penálti' if penalty else ''}!", team, shooter, None, defender, start, end, None, True)
            self._owner(1-team, self._kickoff_player(1-team))
            return
        if on_target:
            self.stats[1-team]["def_"] += 1
            self.pstats[1-team][gk]["def_"] += 1
            self._event(minute, "defesa", f"{self.teams[1-team][gk].nome} defende o remate de {shot_player.nome}.", team, shooter, None, gk, start, end)
            if random.random() < 0.22:
                _, winner_team, winner = self._race(end)
                self._event(minute, "bola_livre", "A defesa larga a bola; começa uma corrida à recarga.", team, shooter, None, gk, end, end, (winner_team, winner))
                self._owner(winner_team, winner, end["x"], end["y"])
            else:
                self._owner(1-team, gk, end["x"], end["y"])
            return
        self._event(minute, "remate", f"{shot_player.nome} remata, mas a bola sai ao lado.", team, shooter, None, defender, start, end)
        if random.random() < 0.28:
            self._corner(minute, team)
        else:
            self._owner(1-team, self._keeper(1-team))

    def _foul(self, minute, attacking_team, attacker, defender):
        defending_team = 1 - attacking_team
        S = self.stats[defending_team]
        S["faltas"] += 1
        self.pstats[defending_team][defender]["faltas"] += 1
        start = {"x": self.ball["x"], "y": self.ball["y"], "z": 0.0}
        self._event(minute, "falta", f"Falta de {self.teams[defending_team][defender].nome} sobre {self.teams[attacking_team][attacker].nome}.", attacking_team, attacker, None, defender)
        player_stat = self.pstats[defending_team][defender]
        aggression = self._attr(defending_team, defender, "agressividade")
        yellow_chance = 0.10 + aggression / 520 + (0.16 if player_stat["amarelos"] else 0)
        red_chance = 0.008 + max(0, aggression - 75) / 1400
        if player_stat["amarelos"] and random.random() < yellow_chance:
            player_stat["amarelos"] += 1
            S["amarelos"] += 1
            player_stat["vermelhos"] += 1
            S["vermelhos"] += 1
            self.players[defending_team][defender]["ativo"] = False
            self._event(minute, "vermelho", f"Segundo amarelo e expulsão para {self.teams[defending_team][defender].nome}.", attacking_team, attacker, None, defender)
        elif random.random() < red_chance:
            player_stat["vermelhos"] += 1
            S["vermelhos"] += 1
            self.players[defending_team][defender]["ativo"] = False
            self._event(minute, "vermelho", f"Cartão vermelho direto para {self.teams[defending_team][defender].nome}.", attacking_team, attacker, None, defender)
        elif random.random() < yellow_chance:
            player_stat["amarelos"] += 1
            S["amarelos"] += 1
            self._event(minute, "amarelo", f"Cartão amarelo para {self.teams[defending_team][defender].nome}.", attacking_team, attacker, None, defender)
        stamina = self._attr(defending_team, defender, "resistencia")
        if random.random() < 0.003 + max(0, 70 - stamina) / 4000:
            player_stat["lesao"] = 1
            S["lesoes"] += 1
            self.players[defending_team][defender]["ativo"] = False
            self._event(minute, "lesao", f"{self.teams[defending_team][defender].nome} lesiona-se no lance e não pode continuar.", attacking_team, attacker, None, defender)
        x, y = self.players[defending_team][defender]["x"], self.players[defending_team][defender]["y"]
        local_u = self._u(attacking_team, x)
        local_v = y if attacking_team == 0 else 1 - y
        in_box = local_u >= 0.84 and abs(local_v - 0.5) <= 0.22
        if in_box:
            self._penalty(minute, attacking_team)
        else:
            self._free_kick(minute, attacking_team, attacker, local_u)

    def _best_taker(self, team, kind):
        candidates = [i for i in range(1, 7) if self._active(team, i)]
        if not candidates:
            return self._keeper(team)
        if kind == "penaltis":
            score = lambda i: (0.46 * self._attr(team, i, "finalizacao") + 0.30 * self._attr(team, i, "compostura")
                               + 0.16 * self._attr(team, i, "bola_parada") + 0.08 * self._attr(team, i, "decisoes"))
        elif kind == "cantos":
            score = lambda i: (0.46 * self._attr(team, i, "bola_parada") + 0.30 * self._attr(team, i, "cruzamento")
                               + 0.16 * self._attr(team, i, "tecnica") + 0.08 * self._attr(team, i, "decisoes"))
        else:
            score = lambda i: (0.58 * self._attr(team, i, "bola_parada") + 0.22 * self._attr(team, i, "tecnica")
                               + 0.12 * self._attr(team, i, "compostura") + 0.08 * self._attr(team, i, "passe"))
        return max(candidates, key=score)

    def _free_kick(self, minute, team, fouled, local_u):
        taker = self._best_taker(team, "livres")
        taker = taker if self._active(team, taker) else fouled
        start = {"x": self.ball["x"], "y": self.ball["y"], "z": 0.0}
        self.players[team][taker]["x"], self.players[team][taker]["y"] = start["x"], start["y"]
        self._owner(team, taker, start["x"], start["y"])
        distance = (1 - local_u) * self.FIELD_X
        self._event(minute, "livre", f"Livre para {self.teams[team][taker].nome}; a equipa prepara a bola parada.", team, taker, None, None, start, start)
        if distance < 33 and abs((self.players[team][taker]["y"] if team == 0 else 1-self.players[team][taker]["y"]) - 0.5) < 0.31:
            self._shot(minute, set_piece=True, taker=taker, label="livre")
        else:
            self._pass(minute, cross=True, set_piece=True)

    def _penalty(self, minute, team):
        taker = self._best_taker(team, "penaltis")
        taker = taker if self._active(team, taker) else self._kickoff_player(team)
        spot_x, spot_y = self._world(team, 0.89, 0.5)
        self.players[team][taker]["x"], self.players[team][taker]["y"] = spot_x, spot_y
        self._owner(team, taker, spot_x, spot_y)
        self._event(minute, "penalti", f"Grande penalidade para {self.names[team]}: {self.teams[team][taker].nome} na marca dos onze metros.", team, taker)
        self._shot(minute, penalty=True, taker=taker)

    def _corner(self, minute, team):
        self.stats[team]["cantos"] += 1
        taker = self._best_taker(team, "cantos")
        taker = taker if self._active(team, taker) else self._kickoff_player(team)
        local_y = 0.035 if random.random() < 0.5 else 0.965
        x, y = self._world(team, 0.96, local_y)
        self.players[team][taker]["x"], self.players[team][taker]["y"] = x, y
        self._owner(team, taker, x, y)
        self._event(minute, "canto", f"Pontapé de canto para {self.names[team]}, batido por {self.teams[team][taker].nome}.", team, taker)
        self._pass(minute, cross=True, set_piece=True)

    def _tick_to_restart(self, minute, team):
        self.pos = team
        self.c = self._kickoff_player(team)
        self._owner(team, self.c, 0.5, 0.5)

    def _finish(self):
        total = sum(t["posse"] for t in self.stats) or 1
        for k in range(2):
            self.stats[k]["posse_pct"] = round(100 * self.stats[k]["posse"] / total)
            goals_against = self.stats[1-k]["golos"]
            won = 1 if self.stats[k]["golos"] > goals_against else -1 if self.stats[k]["golos"] < goals_against else 0
            for i, p in enumerate(self.pstats[k]):
                activity = p["pc"] * 0.012 + p["dri"] * 0.15 + p["des"] * 0.22 + p["inte"] * 0.24 + p["ast"] * 0.60
                rating = 6.0 + p["golos"] * 1.05 + activity - p["perdas"] * 0.06 - p["amarelos"] * 0.32 - p["vermelhos"] * 1.1 + won * 0.18
                if i == self._keeper(k):
                    rating += p["def_"] * 0.28 + (0.6 if goals_against == 0 else 0)
                if self.positions[k][i] in DEFENDER_POSITIONS and goals_against <= 1:
                    rating += 0.35
                p["nota"] = round(self._clamp(rating, 4.0, 10.0), 1)
                highlights = []
                if p["golos"]: highlights.append(f"{p['golos']}G")
                if p["ast"]: highlights.append(f"{p['ast']}A")
                if p["des"] + p["inte"]: highlights.append(f"{p['des'] + p['inte']} rec")
                if p["amarelos"]: highlights.append(f"{p['amarelos']} CA")
                if p["vermelhos"]: highlights.append(f"{p['vermelhos']} CV")
                p["resumo"] = " · ".join(highlights) if highlights else f"{p['pc']} passes completos"
        mvp_team, mvp_player = max(
            ((k, p) for k in range(2) for p in self.pstats[k]),
            key=lambda item: (item[1]["nota"], item[1]["golos"], item[1]["ast"], item[1]["inte"] + item[1]["des"]),
        )
        mvp = {**mvp_player, "equipa": self.names[mvp_team], "eq_idx": mvp_team}
        cronica = self._chronicle()
        for k in range(2):
            self.stats[k]["notas"] = self.pstats[k]
            self.stats[k]["marcadores"] = self.markers[k]
            self.stats[k]["mvp"] = mvp
            self.stats[k]["cronica"] = cronica
        return self.ev, self.stats

    def _chronicle(self):
        parts = []
        for start, end, title in ((1, self.MIN // 2, "1ª Parte"), (self.MIN // 2 + 1, self.MIN, "2ª Parte")):
            goals = [0, 0]
            yellows = [0, 0]
            reds = [0, 0]
            offsides = [0, 0]
            for e in self.ev:
                if not start <= e["m"] <= end:
                    continue
                if e["tipo"] == "golo": goals[e["eq"]] += 1
                elif e["tipo"] == "amarelo": yellows[1-e["eq"]] += 1
                elif e["tipo"] == "vermelho": reds[1-e["eq"]] += 1
                elif e["tipo"] == "fora_de_jogo": offsides[1-e["eq"]] += 1
            score = [sum(1 for e in self.ev if e["tipo"] == "golo" and e["eq"] == k and e["m"] <= end) for k in range(2)]
            detail = []
            if sum(yellows): detail.append(f"{sum(yellows)} cartões amarelos")
            if sum(reds): detail.append(f"{sum(reds)} expulsões")
            if sum(offsides): detail.append(f"{sum(offsides)} foras de jogo após subidas da linha")
            if title == "1ª Parte":
                summary = f"Ao intervalo, {self.names[0]} e {self.names[1]} estão {score[0]}-{score[1]}."
            else:
                summary = f"O encontro termina {score[0]}-{score[1]} após uma segunda parte de duelos e transições."
            parts.append(dict(parte=title, resumo=summary + (" " + "; ".join(detail) + "." if detail else "")))
        return parts

    def jogar(self):
        self._event(0, "apito", "Apita o árbitro: começa o jogo!", self.pos, self.c)
        for minute in range(1, self.MIN + 1):
            for _ in range(self.TICKS):
                self._tick(minute)
            if minute == self.MIN // 2:
                self._event(minute, "apito", "Intervalo.", self.pos, self.c)
                self._tick_to_restart(minute, random.randint(0, 1))
        self._event(self.MIN, "apito", "Fim do jogo!", self.pos, self.c)
        return self._finish()

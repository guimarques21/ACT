"""Simulador online espacial do AC Travanca.

O motor offline continua em match_engine.py. Este motor usa os atributos do
Excel ModoOnline, posicionamento contínuo em metros e uma bola com trajetória.
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


class FootballManagerEngine:
    MIN = 60
    TICKS = 4
    FIELD_X = 105.0
    FIELD_Y = 68.0
    ACTION_SECONDS = 15.0
    PRESSURE_LEVEL = 0.56
    TEMPO_LEVEL = 0

    def __init__(self, name_a, name_b, players_a, players_b, tactic_a, tactic_b, coordinates, position_layout=None):
        self.names = [name_a, name_b]
        self.teams = [players_a, players_b]
        self.tactics = [tactic_a, tactic_b]
        self.coordinates = coordinates
        position_layout = position_layout or POSITION_LAYOUT
        self.positions = [position_layout[tactic_a], position_layout[tactic_b]]
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

    @staticmethod
    def _team_stats():
        return dict(golos=0, posse=0, rem=0, bal=0, def_=0, pc=0, pt=0, des=0, inte=0,
                    faltas=0, amarelos=0, vermelhos=0, impedimentos=0, cantos=0,
                    penaltis=0, lesoes=0, duelos=0, cruzamentos=0, perdas=0)

    def _player_stats(self, team, index):
        p = self.teams[team][index]
        return dict(nome=p.nome, pos="GR" if index == 0 else "/".join(p.pos), posicao=self.positions[team][index],
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
        if position == "MIX":
            need = {k: (POSITION_NEEDS["MC"].get(k, 0) + POSITION_NEEDS["ML"].get(k, 0)) / 2 for k in ALL_ATTRIBUTES}
        else:
            need = POSITION_NEEDS[position]
        if position == "GR":
            weights = {k: 0.45 for k in OUTFIELD_ATTRIBUTES}
            weights.update({k: 1.0 for k in GOALKEEPER_ATTRIBUTES})
        else:
            weights = {k: 1.0 for k in OUTFIELD_ATTRIBUTES}
            weights.update({k: 0.25 for k in GOALKEEPER_ATTRIBUTES})
        for attr, priority in need.items():
            weights[attr] += priority
        profile = sum(self._safe(p.a.get(attr, 50.0)) * weight for attr, weight in weights.items()) / sum(weights.values())
        effective = raw * 0.76 + profile * 0.24
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
                advance = {"GR": 0.0, "D": 0.025, "DC": 0.015, "DL": 0.055, "MC": 0.07,
                           "ML": 0.10, "MIX": 0.085, "A": 0.11, "AW": 0.12}[position]
                target_u = base_u + (advance if attacking else 0.0)
                target_v = base_v
                if attacking:
                    target_u += (ball_u - 0.5) * (0.20 if i else 0.0)
                    target_v += (ball_v - base_v) * (0.25 if position in MIDFIELD_POSITIONS | FORWARD_POSITIONS else 0.14)
                else:
                    target_u += (ball_u - 0.48) * (0.22 if position in DEFENDER_POSITIONS else 0.12)
                    target_v += (ball_v - base_v) * 0.22
                    if position in DEFENDER_POSITIONS:
                        target_u += 0.075
                if position in {"DL", "ML", "AW"}:
                    target_v += -0.085 if base_v < 0.5 else 0.085
                elif position == "MIX":
                    target_v += -0.035 if base_v < 0.5 else 0.035
                target_u = self._clamp(target_u, 0.04, 0.96)
                target_v = self._clamp(target_v, 0.05, 0.95)
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
                reaction = 0.42 - anticipate * 0.002
                if preferred == (team, index):
                    reaction -= 0.14
                if target.get("z", 0.0) >= 3.0:
                    height = self._safe(self.teams[team][index].a.get("altura", 1.75), 1.75)
                    aerial = 0.55 * self._attr(team, index, "cabecemento") + 0.30 * self._attr(team, index, "impulsao") + 0.15 * min(100, height * 52)
                    reaction -= aerial / 420
                arrivals.append((dist / self._speed(team, index) + max(0.08, reaction), team, index))
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
            reach_time = gap / self._speed(1 - team, index) + 0.36 - self._attr(1 - team, index, "antecipacao") * 0.002
            at_ball_time = max(0.0, flight_time * frac)
            if gap < 2.8 and reach_time <= at_ball_time + 0.20:
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
        chance = self._clamp(0.18 + group_skill / 100 * 0.58, 0.28, 0.78)
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
            weight = 1.0 + self._attr(team, i, "visao") / 60 + self._attr(team, i, "decisoes") / 100
            if through:
                weight *= 0.55 + max(0.0, u - source_u) * 3.5 + self._attr(team, i, "sem_bola") / 120
            else:
                weight *= 1.0 + max(-0.12, min(0.12, u - source_u))
            if position == "MC":
                weight *= 1.18
            elif position in {"ML", "MIX", "DL"} and abs(p["y"] - 0.5) > 0.18:
                weight *= 1.12
            elif position == "MIX" and through:
                weight *= 1.14
            if cross:
                weight *= 1.55 if position in FORWARD_POSITIONS else 0.76
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
        start = {"x": self.ball["x"], "y": self.ball["y"], "z": self.ball["z"]}
        receiver_u = self._u(team, target_player["x"])
        receiver_v = target_player["y"] if team == 0 else 1 - target_player["y"]
        if through:
            receiver_u += 0.045 + self._attr(team, receiver, "velocidade") / 1800
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
        if self.c == self._keeper(self.pos):
            self._pass(minute, through=False)
            return
        team, carrier = self.pos, self.c
        u = self._u(team, self.players[team][carrier]["x"])
        pressure = self._pressure(team, carrier)
        position = self.positions[team][carrier]
        can_shoot = u > 0.54
        can_cross = u > 0.59 and abs(self.players[team][carrier]["y"] - 0.5) > 0.21 and position in {"DL", "ML", "AW"}
        weights = [30.0, 20.0, max(2.0, 14 + (u - 0.54) * 62) if can_shoot else 2.0, 10.0 if can_cross else 1.0]
        if position == "MC":
            weights[0] *= 1.22
        if position in {"ML", "DL", "AW"}:
            weights[1] *= 1.22
            weights[3] *= 1.45
        if position in FORWARD_POSITIONS:
            weights[2] *= 1.42
        traits = str(p.a.get("traits", "")).casefold()
        if "finta frequentemente" in traits:
            weights[1] *= 1.45
        action = random.choices(("pass", "dribble", "shot", "cross"), weights)[0]
        defender = self._nearest_defender(team, carrier)
        if action == "pass":
            P["pt"] += 0
            through_chance = 0.12 + self._attr(team, carrier, "visao") / 500
            trait = str(p.a.get("traits", "")).casefold()
            self._pass(minute, through=random.random() < min(0.48, through_chance) or "passes de rutura" in trait)
        elif action == "cross":
            self.stats[team]["cruzamentos"] += 1
            P["pt"] += 0
            self._pass(minute, cross=True)
        elif action == "dribble":
            d = self.teams[1-team][defender]
            dstat = self.pstats[1-team][defender]
            attack = 0.38 * self._attr(team, carrier, "drible") + 0.24 * self._attr(team, carrier, "tecnica") + 0.22 * self._attr(team, carrier, "aceleracao") + 0.16 * self._attr(team, carrier, "velocidade")
            defend = 0.30 * self._attr(1-team, defender, "desarme") + 0.20 * self._attr(1-team, defender, "marcacao") + 0.21 * self._attr(1-team, defender, "antecipacao") + 0.15 * self._attr(1-team, defender, "agilidade") + 0.14 * self._attr(1-team, defender, "forca")
            attack += 3 if position in {"ML", "DL", "MIX", "AW"} else 0
            pressure_mod = self.PRESSURE_LEVEL
            win = random.random() < self._prob(0.49 + (attack - defend) / 115 - pressure_mod * pressure / 110)
            self.stats[team]["duelos"] += 1
            self.stats[1-team]["duelos"] += 1
            if win:
                P["dri"] += 1
                self._event(minute, "drible", f"{p.nome} ultrapassa {d.nome} com um drible.", team, carrier, None, defender)
                local_u, local_v = self._local(team, self.players[team][carrier]["x"], self.players[team][carrier]["y"])
                local_u = min(0.97, local_u + 0.035)
                x, y = self._world(team, local_u, local_v)
                self._owner(team, carrier, x, y)
            else:
                foul_chance = 0.045 + self._attr(1-team, defender, "agressividade") / 680 + pressure_mod * 0.055
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
        u = self._u(team, player["x"])
        y = player["y"] if team == 0 else 1 - player["y"]
        distance = 11.0 if penalty else max(4.0, (1 - u) * self.FIELD_X)
        angle_penalty = abs(y - 0.5) * 28
        defender = self._nearest_defender(team, shooter)
        gk = self._keeper(1-team)
        pressure = self._pressure(team, shooter)
        fin = self._attr(team, shooter, "finalizacao")
        tech = self._attr(team, shooter, "tecnica")
        composure = self._attr(team, shooter, "compostura")
        skill = 0.43 * fin + 0.21 * tech + 0.17 * composure + 0.11 * self._attr(team, shooter, "decisoes") + 0.08 * self._attr(team, shooter, "primeiro_toque")
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

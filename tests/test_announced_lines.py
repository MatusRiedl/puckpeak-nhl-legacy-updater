"""The announced lines (tools/providers/dailyfaceoff.py): who plays centre when two centres share a line."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'tools'))
from providers import dailyfaceoff as D  # noqa: E402


def listed(group, spot, name, number=None):
    return {'group': group, 'spot': spot, 'name': name, 'number': number}


def oilers():
    rows = [listed('f1', 'lw', 'Vasily Podkolzin', 92), listed('f1', 'c', 'Connor McDavid', 97),
            listed('f1', 'rw', 'Leon Draisaitl', 29), listed('f2', 'lw', 'Kasperi Kapanen', 42),
            listed('f2', 'c', 'Ryan Nugent-Hopkins', 93), listed('f2', 'rw', 'Zach Hyman', 18),
            listed('f3', 'lw', 'Alex Formenton', 26), listed('f3', 'c', 'Owen Michaels', 43),
            listed('f3', 'rw', 'Mathieu Joseph', 21), listed('f4', 'lw', 'Max Jones', 46),
            listed('f4', 'c', 'Colton Dach', 34), listed('f4', 'rw', 'Filip Hallander', 19),
            listed('d1', 'ld', 'Shakir Mukhamadullin', 85), listed('d1', 'rd', 'Evan Bouchard', 2),
            listed('d2', 'ld', 'Ryan Shea', 6), listed('d2', 'rd', 'Connor Murphy', 5),
            listed('d3', 'ld', 'Jake Walman', 96), listed('d3', 'rd', 'Ty Emberson', 49),
            listed('g', 'g1', 'Tristan Jarry', 35), listed('g', 'g2', 'Matt Tomkins')]
    for k, who in enumerate(('Zach Hyman', 'Ryan Nugent-Hopkins', 'Leon Draisaitl', 'Connor McDavid', 'Evan Bouchard'), 1):
        rows.append(listed('pp1', f'sk{k}', who))
    for k, who in enumerate(('Connor McDavid', 'Kasperi Kapanen', 'Ryan Shea', 'Connor Murphy'), 1):
        rows.append(listed('pk1', f'sk{k}', who))
    return rows


def ids_of(rows):
    names = sorted({r['name'] for r in rows})
    by_name = {D.matching.norm(n): [(1000 + k, None)] for k, n in enumerate(names)}
    return by_name, {}, {n: 1000 + k for k, n in enumerate(names)}


def test_the_listed_centre_plays_centre_even_when_a_team_mate_is_a_centre_too():
    rows = oilers()
    by_name, by_number, ident = ids_of(rows)
    slots = D.team_slots(rows, by_name, by_number)
    assert (slots['l1lw'], slots['l1c'], slots['l1rw']) == tuple(ident[n] for n in (
        'Vasily Podkolzin', 'Connor McDavid', 'Leon Draisaitl'))
    assert slots['pp1c'] == ident['Connor McDavid'] and slots['pp1rw'] == ident['Leon Draisaitl']
    assert slots['pp1ld'] == ident['Evan Bouchard']          # four forwards and one defenceman: the fourth forward
    assert slots['pp1rd'] == ident['Ryan Nugent-Hopkins']    # fills the defence spot left open
    assert slots['pk4_1c'] == ident['Connor McDavid'] and slots['pk3_1ld'] == ident['Ryan Shea']
    assert 'pp2c' not in slots and 'pk4_2c' not in slots      # units the page does not list are left out


def test_a_group_with_a_player_nhl_com_lacks_is_left_out_and_the_games_fill_it():
    rows = oilers()
    by_name, by_number, ident = ids_of(rows)
    del by_name[D.matching.norm('Colton Dach')]
    slots = D.team_slots(rows, by_name, by_number)
    assert 'l4c' not in slots and 'l4lw' not in slots and 'l1c' in slots
    merged = D.merge({'EDM': {'date': 'd', 'slots': slots}},
                     {'EDM': {'date': 'g', 'games': [1], 'slots': {'l1c': 5, 'l4c': 6, 'pk4_1c': 7}}})['EDM']
    assert merged['slots']['l1c'] == 5                           # announced lines are incomplete: even strength is the games'
    assert 'l:games' in merged['source']


def test_two_players_of_one_name_are_told_apart_by_number():
    by_name = {D.matching.norm('Elias Pettersson'): [(40, 40), (25, 25)]}
    assert D.who(listed('d1', 'ld', 'Elias Pettersson', 25), by_name, {}) == 25
    assert D.who(listed('f1', 'c', 'Elias Pettersson', 40), by_name, {}) == 40
    assert D.who(listed('d1', 'ld', 'Elias Nils Pettersson', 25), by_name, {25: (25, 'pettersson')}) == 25


def test_a_player_the_roster_lacks_never_takes_the_id_of_a_team_mate_with_his_number():
    by_name = {D.matching.norm('Oliver Ekman-Larsson'): [(8475171, 95)]}
    by_number = {95: (8475171, D.matching.norm('Ekman-Larsson'))}
    assert D.who(listed('f3', 'rw', 'Vinni Lettieri', 95), by_name, by_number) is None
    assert D.who(listed('d2', 'ld', 'Oliver Ekman-Larsson', 95), by_name, by_number) == 8475171

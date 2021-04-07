#!/usr/bin/env python3

import sys
import sqlite3
import argparse
import configparser
import csv
from sqlite3 import Error

# Queries
_sql_create_main_table     = """ CREATE TABLE IF NOT EXISTS main (
                                    name integer PRIMARY KEY,
                                    count integer NOT NULL DEFAULT 0
                               ); """
                               
_sql_export_all            = """ SELECT name, count FROM main; """
                            
_sql_count_main_table      = """ SELECT COUNT(*) FROM main; """

_sql_insert_main_table     = """ INSERT INTO main (name, count) VALUES (?,?); """

_sql_count_missing_cards   = """ SELECT COUNT(*) FROM main WHERE count = 0; """

_sql_list_missing_cards    = """ SELECT name FROM main WHERE count = 0; """

_sql_list_duplicate_cards  = """ SELECT name FROM main WHERE count > 1; """

_sql_count_duplicate_cards = """ SELECT IFNULL(SUM(count),0) - COUNT(*) FROM main WHERE count > 1; """

_sql_count_total_cards     = """ SELECT SUM(count) FROM main; """

_sql_count_card            = """ SELECT count FROM main WHERE name = ?; """

_sql_insert_count_card     = """ UPDATE main SET count = ? WHERE name = ?; """


# Init database
class _InitIterCards:
    
    def __init__(self, total_cards, count = 0):
        self.total_cards = total_cards
        self.count = count

    def __iter__(self):
        return self

    def __next__(self):
        self.count += 1
        if self.count > self.total_cards:
            raise StopIteration
        return (self.count, 0)

# Private funcions
def _init_database(db, total_cards):
    cursor = db.cursor()
    cursor.execute(_sql_create_main_table)
    current_count = _get_count(db, _sql_count_main_table)
    if current_count < total_cards:
        cursor.executemany(_sql_insert_main_table, _InitIterCards(total_cards, current_count))
    db.commit()

def _get_count(db, query, *args):
    cursor = db.cursor()
    cursor.execute(query, args)
    return cursor.fetchone()[0]

def _get_list(db, query, *args):
    cursor = db.cursor()
    cursor.execute(query, args)
    list = []
    for row in cursor.fetchall():
        list.append(row[0])
    return list

def _get_select(db, query, *args):
    cursor = db.cursor()
    cursor.execute(query, args)
    return cursor.fetchall()

def _set_data(db, query, *args):
    cursor = db.cursor()
    cursor.execute(query, args)
    db.commit()

def _print_output(output, i=1):
    for item in output:
        print("%s %s: " % ('-'*i, item['label']), end='')
        if isinstance(item['value'], list):
            print()
            _print_output(item['value'], i+1)
        else:
            print("%s" % (item['value']))

def _get_card_position(name, rows_in_page, columns_in_page):
    cards_in_page = rows_in_page * columns_in_page
    position_in_page = ((int(name) - 1) % cards_in_page)
    return [
        {
            'label': 'Pagina',
            'value': ((int(name) - 1) // cards_in_page) + 1
        },
        {
            'label': 'Riga',
            'value': ((position_in_page) // rows_in_page ) + 1
        },
        {
            'label': 'Colonna',
            'value': ((position_in_page) % columns_in_page ) + 1
        }
    ]

# Public functions
def add_card(env, name):
    if env['read_only']:
        return [
        {
            'label': 'Errore',
            'value': 'Modalità sola lettura'
        }
    ]
    if int(name) <= 0 or int(name) > env['total_cards']:
        return [
        {
            'label': 'Errore',
            'value': 'Fuori dal range 0 - %d' % env['total_cards']
        }
    ]
    count = _get_count(env['db'], _sql_count_card, name)
    _set_data(env['db'], _sql_insert_count_card, count+1, name)
    return [
        {
            'label': 'Nuova',
            'value': 'Si' if (count == 0) else 'No'
        },
        {
            'label': 'Posizione carta',
            'value': _get_card_position(int(name) + env['name_offset'], env['rows_in_page'], env['columns_in_page'])
        }
    ]

def delete_card(env, name):
    if env['read_only']:
        return [
        {
            'label': 'Errore',
            'value': 'Modalità sola lettura'
        }
    ]
    if int(name) <= 0 or int(name) > env['total_cards']:
        return [
        {
            'label': 'Errore',
            'value': 'Fuori dal range 0 - %d' % env['total_cards']
        }
    ]
    count = _get_count(env['db'], _sql_count_card, name)
    if count <= 0:
        return [
        {
            'label': 'Errore',
            'value': 'Questa carta non è presente'
        }
    ]
    _set_data(env['db'], _sql_insert_count_card, count-1, name)

def read_card(env,  name):
    if int(name) <= 0 or int(name) > env['total_cards']:
        return [
            {
                'label': 'Errore',
                'value': 'Fuori dal range 0 - %d' % env['total_cards']
            }
        ]
    return [
        {
            'label': 'Quantità carta',
            'value': _get_count(env['db'], _sql_count_card, name)
        },
        {
            'label': 'Posizione carta',
            'value': _get_card_position(int(name) + env['name_offset'], env['rows_in_page'], env['columns_in_page'])
        }
    ]

def global_stats(env):
    missing = _get_count(env['db'], _sql_count_missing_cards)
    total = _get_count(env['db'], _sql_count_total_cards)
    duplicate = _get_count(env['db'], _sql_count_duplicate_cards)
    return [
        {
            'label': 'Carte collezionate',
            'value': env['total_cards'] - missing
        },
        {
            'label': 'Carte da collezionare',
            'value': missing
        },
        {
            'label': 'Totale carte',
            'value': total
        },
        {
            'label': 'Numero doppioni',
            'value': duplicate
        }
    ]

def list_cards(env):
    return [
        {
            'label': 'Carte mancanti',
            'value': ', '.join([str(x) for x in _get_list(env['db'], _sql_list_missing_cards)])
        },
        {
            'label': 'Carte doppie',
            'value': ', '.join([str(x) for x in _get_list(env['db'], _sql_list_duplicate_cards)])
        }
    ]

def export_csv(env, filename):
    with open(filename, 'w') as csvfile:
        csvwriter = csv.DictWriter(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL, fieldnames=['name','count'])
        csvwriter.writeheader()
        for line in _get_select(env['db'], _sql_export_all):
            csvwriter.writerow({
                'name': line[0],
                'count': line[1]
            })

# Menù
_menu_options = {
    
    'i' : {
        'label': 'Inserire una carta',
        'function': add_card,
        'args': [
            {
                'name': 'name',
                'label': 'Nome carta'
            }
        ]
    },
            
    'd' : {
        'label': 'Eliminare una carta',
        'function': delete_card,
        'args': [
            {
                'name': 'name',
                'label': 'Nome carta'
            }
        ]
    },

    'r': {
        'label': 'Leggere una carta',
        'function': read_card,
        'args': [
            {
                'name': 'name',
                'label': 'Nome carta'
            }
        ]
    },
            
    's': {
        'label': 'Statistiche generali',
        'function': global_stats
    },
    
    'l': {
        'label': 'Liste',
        'function': list_cards
    },
    
    'e': {
        'label': 'Esporta CSV lista',
        'function': export_csv,
        'args': [
            {
                'name': 'filename',
                'label': 'Nome file'
            }
        ]
    },
        
}

# Main
if __name__ == '__main__':
    
    argument_parser = argparse.ArgumentParser(description="Tranding Cards Helper")
    argument_parser.add_argument('config_file', help="Config file")
    argument_parser.add_argument('-r', '--read-only', action="store_true", dest="readonly", help="Read only mode")
    args = argument_parser.parse_args()
    
    config_parser = configparser.ConfigParser()
    config_parser.read(args.config_file)
    
    env = {}
    env['total_cards'] = int(config_parser['collection']['total_cards'])
    env['rows_in_page'] = int(config_parser['collection']['rows_in_page'])
    env['columns_in_page'] = int(config_parser['collection']['columns_in_page'])
    env['name_offset'] = int(config_parser['collection']['name_offset'])
    env['read_only'] = bool(args.readonly)
            
    try:
        
        env['db'] = sqlite3.connect(config_parser['database']['file'])
        
        _init_database(env['db'], env['total_cards'])
                
        while True:
            
            for opt in _menu_options:
                print("%s) %s" % (opt, _menu_options[opt]['label']))
            print("q) Esci")
            
            choice = input('Scegli una opzione: ').lower()
            
            if choice == 'q':
                break
            
            if choice not in _menu_options:
                print("Opzione non trovata, riprovare...")
                print()
                continue
            
            function_args = {}
            
            if 'args' in _menu_options[choice]:
                for arg in _menu_options[choice]['args']:
                    function_args[arg['name']] = input("%s: " % (arg['label']))
            
            output = _menu_options[choice]['function'](env, **function_args)
            
            if output != None:
                print()
                _print_output(output)
            
            print()

    except Error as e:
        print(e)
        
    finally:
        if env['db']:
            env['db'].close()

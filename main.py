import json
from pathlib import Path
import PySimpleGUI as gui

def main():
    gui.theme("DarkGrey8")

    # create layout, each line is a new row
    layout =  [
                [gui.FolderBrowse('Tabletop Folder', initial_folder=Path.cwd().as_posix(), key='dir')],
                [gui.Text('Filter Category'), gui.Combo(['Name', 'Tags', 'Description', 'Author'], key='CategoryCombo')],
                [gui.Text('Filter Input'), gui.InputText(key='FilterInputText', tooltip='Current existing tags are: GM-Less, Cards, One-Shot, PbtA, Forged in the Dark and Supplement')],
                [gui.Button('Search')],
                [gui.Multiline(key='SearchResults', size=(53, 6), disabled=True)],
                [gui.Button('Close')] 
    ]

    # finalise layout so we can modify values
    window = gui.Window('File Explorer').layout(layout).finalize()
    directory = window['dir']
    matches = []

    while True:
        event, values = window.read()

        # exit
        if event == gui.WIN_CLOSED or event == 'Close':
            break

        # search by chosen category
        if event == 'Search':
            # if new target direcctory, cache all json files in dir and all subdirs
            if values['dir'] != directory: 
                matches.clear()
                target = Path(values['dir'])         
                for match in Path.glob(target, '**/*.json'):
                    with open(match, 'r', encoding='utf-8') as match_file:
                        if not match_file.readable():
                            continue
                        data = match_file.read()
                        as_json = json.loads(data)
                        matches.append(as_json)
                        match_file.close()
                
                directory = values['dir']

            search_category = values['CategoryCombo'].lower()
            search_for = values['FilterInputText'].lower()
            if not search_category or not search_for:
                continue

            # find json files matching criteria
            results = []
            for file in matches:
                # structure of json files is { "games": ["a": {}] }, so search for root "games" elem
                if not 'games' in file:
                    continue

                for game in file['games']:
                    if search_category in game:
                        # check for substr of input
                        match = game[search_category]

                        # substr exists lambda
                        check = lambda s : s.lower().find(search_for) != -1

                        # check for substr in each entry
                        if type(match) is list:
                            has_match = False
                            for i in match: 
                                if check(i):
                                    # as long as there's a valid match we're good 
                                    has_match = True
                                    break
                            if not has_match:
                                continue
                        elif type(match) is str and not check(match):
                            continue

                        results.append(game['name'])

            # grab multiline to update with results
            widget = window['SearchResults']

            # no matches, clear it out
            if not results:
                widget.update(value='')
                continue

            # add all the matches
            widget.update(value='\n'.join(results))

    window.close()

if __name__ == '__main__':
    main()

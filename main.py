import json
import glob

from pathlib import Path
import PySimpleGUI as gui

SETTINGS_FILE = "folder_indexer_settings.json"
SETTINGS_LAST_DIRECTORY_ENTRY = "last_used_folder_location"
EXECUTING_DIRECTORY = Path.cwd().as_posix()

# loads value of SETTINGS_LAST_DIRECTORY_ENTRY from SETTINGS_FILE
# attempts to create file and entry based on executed file path if not found
def load_last_used_directory():
    ret = ""
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as settings:
            if not settings.readable():
                raise IOError

            data = json.load(settings)
            ret = data[SETTINGS_LAST_DIRECTORY_ENTRY]
            settings.close()
    except FileNotFoundError:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as settings:
            if not settings.writable():
                raise IOError

            json.dump({
                SETTINGS_LAST_DIRECTORY_ENTRY: EXECUTING_DIRECTORY
            }, settings)

            ret = EXECUTING_DIRECTORY
            settings.close()
    except (OSError, IOError) as err:
        gui.popup_error('Error loading or creating settings file, try running as admin.')
    
    return ret

# gets all the root labels in a json file
# e.g.  "a": { "b": "1", "c": "2" }, "z": "1"
#       would return ["z", "c", "b", "a"]
# used to dynamically build filter categories
def get_root_keys(json_data):
    res = []
    for key in json_data.keys():
        # it's not already in our list of root nodes
        if not key in res:
            res.append(key)
        
    return res

# returns list<json files in dir and all subdirectories>, list<root labels>
def cache_json(directory):
    res = []
    roots = []

    target = Path(directory)
    all_json_files = Path.glob(target, '**/*.json')

    #max_size = all_json_files.size()

    for match in all_json_files:
        # TODO: find a more elegant solution
        if match == SETTINGS_FILE:
            continue

        try: 
            with open(match, 'r', encoding='utf-8') as match_file:
                if not match_file.readable():
                    raise IOError

                data = json.load(match_file)
                roots = get_root_keys(data)

                res.append(data)
                match_file.close()

            #progress_bar += 1
        except (OSError, IOError) as err:
            gui.popup_error('Error loading json files, try running as admin.')
        except json.JSONDecodeError as err:
            gui.popup_error('Error converting json file to dict.')
    
    return res, roots

# call cache_json and update SETTINGS_LAST_DIRECTORY_ENTRY
# then, update filter categories to match root node labels
# returns only json matches
def cache_and_update(directory, widget):
    root_nodes = []
    matches = []
    matches, root_nodes = cache_json(directory)

    try:
        with open(SETTINGS_FILE, 'r+') as settings:
            if not settings.writable():
                raise IOError
            
            data = json.load(settings)

            if data[SETTINGS_LAST_DIRECTORY_ENTRY] != directory:
                data[SETTINGS_LAST_DIRECTORY_ENTRY] = directory
            
                settings.seek(0)
                settings.truncate()

                json.dump(data, settings)

            settings.close()
    except (OSError, IOError) as err:
        gui.popup_error('Error writing to settings file, try running as admin.')
    except json.JSONDecodeError as err:
        gui.popup_error('Error converting json file to dict.')

    widget.update(values=root_nodes)
    return matches

def main():
    gui.theme("DarkGrey8")

    loaded_directory = load_last_used_directory()

    # create layout, each line is a new row
    layout =  [
                [gui.InputText(key="FolderLocation", default_text=loaded_directory, disabled=True)],
                # Target folder info
                [gui.FolderBrowse('Browse', key='Directory', target=(-1, 0), initial_folder=loaded_directory)],
                # Categories to filter for
                [gui.Text('Filter Category'), gui.Combo(values=[], key='FilterCategory', size=(40, 4))],
                # Input for category
                [gui.Text('Filter Input'), gui.InputText(key='FilterInputText', tooltip='Add multiple by seperating through commas.')],
                # AND, NOT, OR
                [gui.Combo(['Must Include', 'Must Not Include'], key='FilterType')],
                [gui.Multiline(key='FullFilter', size=(53, 1), disabled=True)],
                # Append filter to fuilter-builder
                [gui.Button('Append', tooltip='Adds the filter text for the category to the overall filter.')],
                # Undo and reset for the filter
                [gui.Button('Undo Last Append'), gui.Button('Reset Filter')],
                [gui.Button('Search')],
                #TODO: Get this working, seems really finnicky and I'd rather just get filters done for now.
                #[gui.ProgressBar(max_value=100, orientation='horizontal', size=(53, 1), key='SearchProgress')],
                [gui.Multiline(key='SearchResults', size=(53, 6), disabled=True)],
                [gui.Button('Close')] 
    ]

    # finalise layout so we can modify values
    window = gui.Window('File Explorer', layout, finalize=True)

    # cached json files
    matches = []

    # try and load json files from the last folder the user loaded
    matches = cache_and_update(window['FolderLocation'].get(), window['FilterCategory'])

    # current built filter
    current_filter = []
    update_filter = lambda : window['FullFilter'].update(value='\n'.join(str(it) for it in current_filter))

    # unfortunately FolderBrowse doesn't trigger an event when it updates, so this is the temp solution
    last_directory = window['FolderLocation'].get()

    while window:
        event, values = window.read()
        
        # exit
        if event in (gui.WIN_CLOSED, 'Exit'):
            break

        # update cached json files on directory change
        # see above comment
        folder_loc = values["FolderLocation"]
        if folder_loc != last_directory:
            root_nodes = []          
            matches = cache_and_update(folder_loc, window['FilterCategory'])
            last_directory = folder_loc
  
        if event == 'Append':
            current_filter.append({
                "Category": values['FilterCategory'],
                "Type": values['FilterType'],
                "Criteria": values['FilterInputText']
            })

            window['FilterInputText'].update(value='')
            update_filter()
        elif event == "Undo Last Append" and current_filter:
            current_filter.pop()
            update_filter()
        elif event == "Reset Filter":
            current_filter = []
            update_filter()
        elif event == "Search":
            if not current_filter:
                gui.popup_error("You don't have any search criteria!")
                continue
            
            # lambda to check if substring 'sub' exists in 's'
            substring_exists = lambda s, sub : s.lower().find(sub) != -1

            # matching results
            results = []

            for file in matches:
                good_result = False

                # enumerate each filter on each file
                for flt in current_filter:
                    # search for matching category
                    if flt["Category"] in file:
                        # check if filter criteria matches (even if partially) 
                        # if found and we want it there, tentatively label this a good result but still iterate through the other criteria
                        found = substring_exists(file[flt["Category"]], flt["Criteria"])
                            
                        if flt["Type"] == "Must Include":
                            good_result = found
                        else:
                            good_result = not found

                        # no point iterating if it fails any criteria
                        if not good_result:
                            break

                if good_result:
                    # way easier to read this way
                    if "Name" in file:
                        results.append(file["Name"])
                    else:
                        results.append(file)
            
            # display results in box regardless of if we got any
            window['SearchResults'].update(value='\n'.join(results))

            # clear out filter
            current_filter = []
            update_filter()

    window.close()


if __name__ == '__main__':
    main()

import json
import time
import pytz

from datetime import datetime
from shapely.geometry import LineString


def read_json(file_path):
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Error reading JSON file: {e}")
        return None


def determination_of_coordinates(JSON_FILE):
    EXT_COORDINATES = JSON_FILE["eventSpecific"]["nnDetect"]["10_8_3_203_rtsp_camera_3"]["cfg"]["cross_lines"][0][
        "ext_line"]
    INT_COORDINATES = JSON_FILE["eventSpecific"]["nnDetect"]["10_8_3_203_rtsp_camera_3"]["cfg"]["cross_lines"][0][
        "int_line"]
    EXT_COORDINATES = scale_conversion(EXT_COORDINATES)
    INT_COORDINATES = scale_conversion(INT_COORDINATES)
    INT_LINE = LineString([(INT_COORDINATES[0], INT_COORDINATES[1]), (INT_COORDINATES[2], INT_COORDINATES[3])])
    EXT_LINE = LineString([(EXT_COORDINATES[0], EXT_COORDINATES[1]), (EXT_COORDINATES[2], EXT_COORDINATES[3])])
    FRAMES = JSON_FILE["eventSpecific"]["nnDetect"]["10_8_3_203_rtsp_camera_3"]["frames"]
    return INT_LINE, EXT_LINE, FRAMES


def scale_conversion(coordinates):
    box_width, box_higth = 836, 470
    frame_width, frame_higth = 640, 360
    x1, x2 = (coordinates[0] / box_width) * frame_width, (coordinates[2] / 836) * 640
    y1, y2 = (coordinates[1] / box_higth) * frame_higth, (coordinates[3] / 470) * 360
    coordinates[:4] = x1, y1, x2, y2
    return coordinates


def scaning_frames(INT_LINE, EXT_LINE, FRAMES, incoming_visitors):
    for frame_data in FRAMES.values():
        timestamp = frame_data['timestamp']
        detected_people = frame_data["detected"]["person"]
        for person_data in detected_people:
            if len(person_data) > 5:
                key = list(person_data[-1].keys())[0]
                track_id = person_data[-1][key].get("track_id")
                if track_id is not None:  # Проверка на наличие track_id
                    x1, y1, x2, y2 = person_data[:4]
                    diagonal_line_visitor = LineString([(x1, y1), (x2, y2)])
                    if track_id not in incoming_visitors:
                        if not diagonal_line_visitor.intersection(INT_LINE).is_empty:
                            incoming_visitors[track_id] = []
                            incoming_visitors[track_id].append({timestamp: "INT"})
                        elif not diagonal_line_visitor.intersection(EXT_LINE).is_empty:
                            incoming_visitors[track_id] = []
                            incoming_visitors[track_id].append({timestamp: "EXT"})
                    else:
                        if not diagonal_line_visitor.intersection(EXT_LINE).is_empty:
                            previos_time, previos_action = (
                                list(incoming_visitors[track_id][-1].items())[0][0],
                                list(incoming_visitors[track_id][-1].items())[0][1]
                            )
                            if previos_action != "EXT":
                                incoming_visitors[track_id].append({timestamp: "EXT"})
                            else:
                                if timestamp - previos_time < 3:
                                    incoming_visitors[track_id][-1] = {timestamp: "EXT"}
                                else:
                                    incoming_visitors[track_id].append({timestamp: "EXT"})
                        if not diagonal_line_visitor.intersection(INT_LINE).is_empty:
                            previos_time, previos_action = (
                                list(incoming_visitors[track_id][-1].items())[0][0],
                                list(incoming_visitors[track_id][-1].items())[0][1]
                            )
                            if previos_action != "INT":
                                incoming_visitors[track_id].append({timestamp: "INT"})
                            else:
                                if timestamp - previos_time < 3:
                                    incoming_visitors[track_id][-1] = {timestamp: "INT"}
                                else:
                                    incoming_visitors[track_id].append({timestamp: "INT"})


def people_counting(incoming_visitors, customers):
    entry_count = 0
    exit_count = 0
    visitors_in_shop = 0
    for visitor, value in incoming_visitors.items():
        timezone = pytz.timezone('Europe/Moscow')
        if len(value) == 2:
            time_action_0, action_0 = list(value[0].items())[0][0], list(value[0].items())[0][1]
            time_action_1, action_1 = list(value[1].items())[0][0], list(value[1].items())[0][1]
            if action_0 == "EXT" and action_1 == "INT":
                customers[visitor] = []
                exit_count += 1
                visitors_in_shop -= 1
                dt_object_exit = datetime.fromtimestamp(time_action_0, tz=timezone).strftime("%Y-%m-%d %H:%M:%S")
                customers[visitor].extend(
                    [f"вышел в {dt_object_exit} проведенное время в магазине "
                     f"установить не удалось"]
                )
            elif action_0 == "INT" and action_1 == "EXT":
                customers[visitor] = []
                entry_count += 1
                visitors_in_shop += 1
                dt_object = datetime.fromtimestamp(time_action_0, tz=timezone).strftime("%Y-%m-%d %H:%M:%S")
                customers[visitor].extend(
                    [f"вошел в {dt_object}"])
        elif len(value) > 2:
            customers[visitor] = []
            actions = []
            for element in value:
                actions.append(list(element.values())[0])
            if actions.count("INT") >= 2 and actions.count("EXT") >= 2:
                if actions[0] == "INT" and actions[-1] == "INT":
                    time_entry = list(value[0].items())[0][0]
                    time_exit = list(value[-1].items())[0][0]
                    dt_object_entry = datetime.fromtimestamp(time_exit, tz=timezone).strftime("%Y-%m-%d %H:%M:%S")
                    dt_object_exit = datetime.fromtimestamp(time_exit, tz=timezone).strftime("%Y-%m-%d %H:%M:%S")
                    entry_count += 1
                    exit_count += 1
                    customers[visitor].extend([f" вошел в {dt_object_entry}"])
                    customers[visitor].extend(
                        [
                            f"вышел в {dt_object_exit} проведенное время "
                            f"в магазине: {round(time_exit - time_entry, 3)} секунд"]
                    )
            else:
                previos_element = actions[0]
                for index, element in enumerate(actions[1:], start=1):
                    current_element = element
                    if previos_element != current_element:
                        if current_element == "INT":
                            exit_count += 1
                            visitors_in_shop -= 1
                            time_exit = list(value[index].items())[0][0]
                            dt_object_exit = datetime.fromtimestamp(time_exit, tz=timezone).strftime("%Y-%m-%d %H:%M:%S")
                            customers[visitor].extend(
                                [
                                    f"вышел в {dt_object_exit} проведенное время в магазине "
                                    f"установить не удалось"]
                            )
                        else:
                            entry_count += 1
                            visitors_in_shop += 1
                            time_exit = list(value[index].items())[0][0]
                            dt_object_entry = datetime.fromtimestamp(time_exit, tz=timezone).strftime("%Y-%m-%d %H:%M:%S")
                            customers[visitor].extend([f"вошел в {dt_object_entry}"])
                    previos_element = current_element
    return entry_count, exit_count, visitors_in_shop


def main():
    start_time = time.time()
    file_path = "detections.json"
    JSON_FILE = read_json(file_path)
    if JSON_FILE:
        INT_LINE, EXT_LINE, FRAMES = determination_of_coordinates(JSON_FILE)

        incoming_visitors = {}
        customers = {}
        scaning_frames(INT_LINE, EXT_LINE, FRAMES, incoming_visitors)

        entry_count, exit_count, visitors_in_shop = people_counting(incoming_visitors, customers)

        print(f"Человек вошло: {entry_count}")
        print(f"Человек вышло: {exit_count}")
        print(f"Людей в магазине: {visitors_in_shop}")
        end_time = time.time()
        print("Работа кода составила", round(end_time - start_time, 3), "sec")


if __name__ == '__main__':
    main()

import json
import pyxel
import math
from datetime import datetime, timedelta

# Constants
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
TIME_SCALE_OPTIONS = [2, 8, 10, 12, 18]  # Speed options (x real speed)
TIME_SCALE_INDEX = 2  # Default to 60x (index 2 in the options)
TIME_SCALE = TIME_SCALE_OPTIONS[TIME_SCALE_INDEX]  # Current time scale
LEFT_PANE_WIDTH = 300
RIGHT_PANE_WIDTH = 500
BUTTON_HEIGHT = 30
COURSE_HEIGHT = 400
RANKING_HEIGHT = 500
RANKING_ANIMATION_SPEED = 5  # Speed of ranking animation
TEAM_COLORS = [
    (8, 8),    # Red
    (9, 9),    # Orange
    (10, 10),  # Yellow
    (11, 11),  # Green
    (12, 12),  # Cyan
    (13, 13),  # Blue
    (14, 14),  # Purple
    (3, 3),    # Dark Blue
    (4, 4),    # Brown
    (5, 5),    # Dark Purple
    (6, 6),    # Dark Green
    (7, 7),    # White
    (0, 0),    # Black
    (1, 1),    # Navy
    (2, 2),    # Maroon
    (8, 0),    # Red + Black
    (9, 0),    # Orange + Black
    (10, 0),   # Yellow + Black
    (11, 0),   # Green + Black
    (12, 0),   # Cyan + Black
]

# Section distances in km
SECTION_DISTANCES = [
    21.3,  # Section 1
    23.1,  # Section 2
    21.4,  # Section 3
    20.9,  # Section 4
    20.8,  # Section 5
    20.8,  # Section 6
    21.3,  # Section 7
    21.4,  # Section 8
    23.1,  # Section 9
    23.0,  # Section 10
]

KURIAGE_SECONDS = [
    600,
    600,
    900,
    900,
    9999,
    1200,
    1200,
    1200,
    1200,
    1200
]

# Total distance for outward and return journeys
OUTWARD_DISTANCE = sum(SECTION_DISTANCES[:5])
RETURN_DISTANCE = sum(SECTION_DISTANCES[5:])
MAX_DISTANCE = max(OUTWARD_DISTANCE, RETURN_DISTANCE)

class HakoneEkidenViewer:
    def __init__(self):
        # Load data
        with open("hakone101_runners.json", "r", encoding="utf-8") as f:
            self.data = json.load(f)
        
        # Initialize variables
        self.is_playing = False
        self.current_time = 0  # Time in seconds
        self.last_update_time = 0  # Last update time in seconds
        self.is_outward = True  # True for outward (1-5), False for return (6-10)
        self.team_positions = []  # List of team positions
        self.max_time = 0         # Maximum time in seconds
        
        # Process data
        self.process_data()
        
        # Initialize Pyxel
        pyxel.init(SCREEN_WIDTH, SCREEN_HEIGHT, title="Hakone Ekiden Viewer")
        pyxel.mouse(True)
        
        # Start the app
        pyxel.run(self.update, self.draw)
    
    def process_data(self):
        # Convert time strings to seconds and calculate speeds
        for i in range(len(self.data)):
            self.data[i]["delay"] = min(600, self.data[i]["delay"])
        for team in self.data:
            for i, runner in enumerate(team["runners"]):
                # Parse time string (e.g., "1時間02分51秒")
                time_parts = runner["record"].replace("時間", ":").replace("分", ":").replace("秒", "").split(":")
                if len(time_parts) == 3:
                    hours, minutes, seconds = map(int, time_parts)
                else:
                    hours = 0
                    minutes, seconds = map(int, time_parts)
                
                total_seconds = hours * 3600 + minutes * 60 + seconds
                runner["seconds"] = total_seconds
                
                # Calculate speed (km/s)
                section_distance = SECTION_DISTANCES[i]
                runner["speed"] = section_distance / total_seconds
        
        # Caluculate 
        self.calulate_kuriage_time()
        
        # Calculate maximum time
        self.calculate_max_time()
        
        # Initialize team positions and rankings
        self.initialize_positions()
    
    def calculate_max_time(self):
        # Calculate the maximum time needed for all teams to complete the course
        outward_times = []
        return_times = []
        
        for team in self.data:
            outward_time = sum(runner["seconds"] for runner in team["runners"][:5])
            return_time = sum(runner["seconds"] for runner in team["runners"][5:]) + team["delay"]
            outward_times.append(outward_time)
            return_times.append(return_time)
        
        self.max_outward_time = max(outward_times)
        self.max_return_time = max(return_times)
        self.max_time = max(self.max_outward_time, self.max_return_time)
    
    def calulate_kuriage_time(self):
        # Calculate minimum time from top at the start of each section
        self.kuriage_seconds = []
        for i in range(10):
            min_time = float('inf')
            for team in self.data:
                if i < 5:
                    time = sum(runner["seconds"] for runner in team["runners"][:i+1])
                else:
                    time = sum(runner["seconds"] for runner in team["runners"][5:i+1]) + team["delay"]
                if time < min_time:
                    min_time = time
            self.kuriage_seconds.append(min_time + KURIAGE_SECONDS[i])

        # update runner['seconds'] to be the time from the start of the section
        for team in self.data:
            for i, runner in enumerate(team["runners"][:-1]):
                runner['kuriage'] = 0
                if i < 5:
                    whole_time = sum(runner["seconds"] - runner['kuriage'] for runner in team["runners"][:i+1])
                    if whole_time > self.kuriage_seconds[i]:
                        runner["kuriage"] = whole_time - self.kuriage_seconds[i]
                else:
                    whole_time = sum(runner["seconds"] for runner in team["runners"][5:i+1]) + team["delay"]
                    if whole_time > self.kuriage_seconds[i]:
                        runner["kuriage"] = whole_time - self.kuriage_seconds[i]

    def initialize_positions(self):
        # Initialize team positions at time 0
        self.team_positions = []
        for team_idx, team in enumerate(self.data):
            self.team_positions.append({
                "team_idx": team_idx,
                "university": team["university"],
                "distance": 0,
                "section": 0 if self.is_outward else 5,
                "color": TEAM_COLORS[team_idx % len(TEAM_COLORS)],
                "display_y": 130 + team_idx * 20,  # For ranking animation
                "target_y": 130 + team_idx * 20    # For ranking animation
            })
        
        # Initialize rankings
        self.update_rankings()
    
    def update_rankings(self):
        # Sort teams by distance
        self.team_positions = sorted(self.team_positions, key=lambda x: x["distance"], reverse=True)
        
        # Update target y positions for animation
        for i, team in enumerate(self.team_positions):
            team["target_y"] = 130 + i * 20
    
    def calculate_positions(self, time):
        # Calculate team positions at the given time
        for team_idx, team in enumerate(self.data):
            for pos in self.team_positions:
                if pos["team_idx"] == team_idx:
                    position = pos
                    break
            # position = self.team_positions[team_idx]
            assert pos['university'] == team['university']
            
            # Determine which sections to consider based on outward/return
            start_section = 0 if self.is_outward else 5
            end_section = 5 if self.is_outward else 10
            
            # Reset position if journey changed
            if (self.is_outward and position["section"] >= 5) or (not self.is_outward and position["section"] < 5):
                position["distance"] = 0
                position["section"] = start_section
            
            # Calculate distance covered
            remaining_time = time
            if not self.is_outward:
                remaining_time = max(0, remaining_time - self.data[team_idx]["delay"])
            distance = 0
            current_section = start_section
            
            while remaining_time > 0 and current_section < end_section:
                runner = team["runners"][current_section]
                section_time = runner["seconds"]
                
                if remaining_time >= section_time - runner.get('kuriage', 0):
                    # Runner completed the section
                    distance += SECTION_DISTANCES[current_section]
                    remaining_time -= section_time
                    current_section += 1
                else:
                    # Runner is still in the section
                    distance += remaining_time * runner["speed"]
                    remaining_time = 0
                
            position["distance"] = distance
            position["section"] = min(current_section, end_section - 1)
        
        # Update rankings
        self.update_rankings()
    
    def change_speed(self, increase=True):
        # Change the playback speed
        global TIME_SCALE_INDEX, TIME_SCALE
        if increase and TIME_SCALE_INDEX < len(TIME_SCALE_OPTIONS) - 1:
            TIME_SCALE_INDEX += 1
        elif not increase and TIME_SCALE_INDEX > 0:
            TIME_SCALE_INDEX -= 1
        
        TIME_SCALE = TIME_SCALE_OPTIONS[TIME_SCALE_INDEX]
    
    def update(self):
        # Handle mouse input
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            mouse_x, mouse_y = pyxel.mouse_x, pyxel.mouse_y
            
            # Play/Pause button
            if 10 <= mouse_x <= 110 and 10 <= mouse_y <= 10 + BUTTON_HEIGHT:
                self.is_playing = not self.is_playing
            
            # Outward/Return toggle button
            if 120 <= mouse_x <= 270 and 10 <= mouse_y <= 10 + BUTTON_HEIGHT:
                self.is_outward = not self.is_outward
                self.current_time = 0
                self.initialize_positions()
            
            # Speed decrease button
            if 280 <= mouse_x <= 310 and 10 <= mouse_y <= 10 + BUTTON_HEIGHT:
                self.change_speed(increase=False)
            
            # Speed increase button
            if 380 <= mouse_x <= 410 and 10 <= mouse_y <= 10 + BUTTON_HEIGHT:
                self.change_speed(increase=True)
            
            # Time bar
            if 10 <= mouse_x <= SCREEN_WIDTH - 10 and 50 <= mouse_y <= 70:
                # Calculate time based on click position
                click_ratio = (mouse_x - 10) / (SCREEN_WIDTH - 20)
                max_time = self.max_outward_time if self.is_outward else self.max_return_time
                self.current_time = click_ratio * max_time
                self.calculate_positions(self.current_time)
        
        # Update time if playing
        if self.is_playing:
            # Update time
            now = datetime.now().timestamp()
            if self.last_update_time == 0:
                self.last_update_time = now
            self.current_time += TIME_SCALE
            max_time = self.max_outward_time if self.is_outward else self.max_return_time
            
            # Stop at the end
            if self.current_time > max_time:
                self.current_time = max_time
                self.is_playing = False
            
            # Calculate positions
            self.calculate_positions(self.current_time)
        else:
            self.last_update_time = 0
        
        # Animate ranking positions
        for team in self.team_positions:
            if abs(team["display_y"] - team["target_y"]) > RANKING_ANIMATION_SPEED:
                if team["display_y"] < team["target_y"]:
                    team["display_y"] += RANKING_ANIMATION_SPEED
                else:
                    team["display_y"] -= RANKING_ANIMATION_SPEED
            else:
                team["display_y"] = team["target_y"]
    
    def draw(self):
        pyxel.cls(7)  # Clear screen with white
        
        # Draw UI elements
        self.draw_controls()
        self.draw_time_bar()
        self.draw_rankings()
        self.draw_course()
    
    def draw_controls(self):
        # Play/Pause button
        pyxel.rect(10, 10, 100, BUTTON_HEIGHT, 13)
        
        # Draw play/pause icon
        if self.is_playing:
            # Pause icon (two vertical bars)
            pyxel.rect(20, 15, 5, 20, 7)
            pyxel.rect(30, 15, 5, 20, 7)
            pyxel.text(45, 20, "STOP", 7)
        else:
            # Play icon (triangle)
            for i in range(15):
                pyxel.line(20, 25 - i, 20, 25 + i, 7)
                pyxel.line(20, 25 - i, 20 + i, 25, 7)
                pyxel.line(20, 25 + i, 20 + i, 25, 7)
            pyxel.text(45, 20, "PLAY", 7)
        
        # Outward/Return toggle button
        pyxel.rect(120, 10, 150, BUTTON_HEIGHT, 12)
        journey_text = "OURO (1-5)" if self.is_outward else "HUKURO (6-10)"
        pyxel.text(130, 20, journey_text, 7)
        
        # Speed control buttons
        pyxel.rect(280, 10, 30, BUTTON_HEIGHT, 5)
        pyxel.text(290, 20, "-", 7)
        
        pyxel.rect(315, 10, 60, BUTTON_HEIGHT, 11)
        pyxel.text(320, 20, f"{TIME_SCALE}x SPEED", 7)
        
        pyxel.rect(380, 10, 30, BUTTON_HEIGHT, 3)
        pyxel.text(390, 20, "+", 7)
        
        # Current time display
        hours, remainder = divmod(int(self.current_time), 3600)
        minutes, seconds = divmod(remainder, 60)
        time_str = f"TIME: {hours:02d}:{minutes:02d}:{seconds:02d}"
        pyxel.text(430, 20, time_str, 0)
    
    def draw_time_bar(self):
        # Draw time bar background
        pyxel.rect(10, 50, SCREEN_WIDTH - 20, 20, 13)
        
        # Draw progress
        max_time = self.max_outward_time if self.is_outward else self.max_return_time
        progress_width = int((self.current_time / max_time) * (SCREEN_WIDTH - 20))
        pyxel.rect(10, 50, progress_width, 20, 8)
        
        # Draw time markers
        for i in range(6):
            marker_x = 10 + (SCREEN_WIDTH - 20) * i / 5
            pyxel.line(marker_x, 50, marker_x, 70, 7)
            
            marker_time = max_time * i / 5
            hours, remainder = divmod(int(marker_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours:02d}:{minutes:02d}"
            pyxel.text(marker_x - 10, 75, time_str, 0)
    
    def draw_rankings(self):
        # Draw rankings in the left pane
        pyxel.rect(0, 100, LEFT_PANE_WIDTH, RANKING_HEIGHT, 7)
        pyxel.text(10, 110, "ORDER", 0)
        
        # Draw team rankings with animation
        for i, team in enumerate(self.team_positions):
            y = team["display_y"]
            university = team["university"]
            color = team["color"]
            
            # Draw rank and university name
            pyxel.rect(10, y, 20, 16, color[0])
            pyxel.text(15, y + 5, str(i + 1), 7)
            pyxel.text(40, y + 5, university, 0)
            
            # Draw current section and runner name
            section = team["section"]
            current_section = section + 1
            runner_name = self.data[team["team_idx"]]["runners"][section]["runner_name"]
            pyxel.text(150, y + 5, f"{current_section}: {runner_name}", 0)
    
    def draw_course(self):
        # Draw course in the right pane
        pyxel.rect(LEFT_PANE_WIDTH, 100, RIGHT_PANE_WIDTH, COURSE_HEIGHT, 7)
        
        # Draw section markers
        section_width = RIGHT_PANE_WIDTH / 5
        for i in range(6):
            x = LEFT_PANE_WIDTH + i * section_width
            pyxel.line(x, 100, x, 100 + COURSE_HEIGHT, 13)
            
            # Label sections
            if i < 5:
                section_num = i + 1 if self.is_outward else i + 6
                pyxel.text(x + 10, 110, f"{section_num}KU", 0)
                
                # Show section distance
                distance = SECTION_DISTANCES[section_num - 1]
                pyxel.text(x + 10, 120, f"{distance}km", 0)
        
        # Draw runners
        for i, position in enumerate(self.team_positions):
            # Calculate x position based on distance
            journey_distance = OUTWARD_DISTANCE if self.is_outward else RETURN_DISTANCE
            x_ratio = position["distance"] / journey_distance
            x = LEFT_PANE_WIDTH + x_ratio * RIGHT_PANE_WIDTH
            
            # Calculate y position (stagger runners vertically)
            team_idx = position["team_idx"]
            # y = 150 + team_idx * 10
            y = position["display_y"]
            
            # Draw runner
            color = position["color"]
            pyxel.circ(x, y, 5, color[0])
            
            # Draw team number and university name
            pyxel.text(x - 2, y - 10, position['university'], color[1])
            # pyxel.text(x - 2, y - 10, str(team_idx + 1), color[1])
            
            # Draw current section and runner name
            section = position["section"]
            current_section = section + 1
            
            # Only show runner name if mouse is over the runner
            if (pyxel.mouse_x - x) ** 2 + (pyxel.mouse_y - y) ** 2 < 100:  # Within 10 pixels
                runner_name = self.data[team_idx]["runners"][section]["runner_name"]
                university = self.data[team_idx]["university"]
                record = self.data[team_idx]["runners"][section]["record"]
                
                # Draw info box
                pyxel.rect(x + 10, y - 15, 150, 40, 13)
                pyxel.text(x + 15, y - 10, f"{university}", 0)
                pyxel.text(x + 15, y, f"{current_section}KU: {runner_name}", 0)
                pyxel.text(x + 15, y + 10, f"RECORD: {record}", 0)
            # else:
            #     pyxel.text(x - 2, y + 8, str(position['distance']), 0)
        
        # Draw legend
        # pyxel.text(LEFT_PANE_WIDTH + 10, COURSE_HEIGHT + 110, "操作方法:", 0)
        # pyxel.text(LEFT_PANE_WIDTH + 10, COURSE_HEIGHT + 125, "- 再生/停止ボタン: アニメーションを再生/停止", 0)
        # pyxel.text(LEFT_PANE_WIDTH + 10, COURSE_HEIGHT + 140, "- 往路/復路ボタン: 往路(1-5区)と復路(6-10区)を切り替え", 0)
        # pyxel.text(LEFT_PANE_WIDTH + 10, COURSE_HEIGHT + 155, "- 速度調整: +/-ボタンで再生速度を変更", 0)
        # pyxel.text(LEFT_PANE_WIDTH + 10, COURSE_HEIGHT + 170, "- タイムバー: クリックして時間を変更", 0)
        # pyxel.text(LEFT_PANE_WIDTH + 10, COURSE_HEIGHT + 185, "- ランナー: マウスオーバーで詳細表示", 0)

# Run the application
if __name__ == "__main__":
    HakoneEkidenViewer()

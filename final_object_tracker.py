#!/usr/bin/env python2.6

# computation libraries 
import cv
import math
import os
import pickle
import sys
import time
import csv
# interface libraries
from PySide.QtCore import *
from PySide.QtGui import *

###########################
#     MOTION TRACKING     #
###########################
# data structure to store velocity, acceleration, distance traveled, and any other computer parameters 
class Speed():
    # minimum requirements to keep the speed object lightweight for the recording phase
    def __init__(self):
	self.start_time = 0.0
	self.stop_time = 0.0
        # folder in which we will save this object
	self.out_folder = ""
	# object's x-coordinate and y-coordinate, and time, respectively 
	self.x = [0.0]
	self.y = [0.0]
	self.t = []

    # append values to the appropriate lists
    def add_pos(self, x_val, y_val, timestep):
	self.x.append(float(x_val))
	self.y.append(float(y_val))
	self.t.append(float(timestep))

    # based on the amount of time that has passed, update all fields
    # timestep is a decimal amount of time in seconds	
    def update(self):
	self.metrics = {}
	parameters_to_track = ["x_pos", "y_pos", "v_x", "v_y", "a_x", "a_y", "distance", "time", "v_net", "a_net"]
	# in first time step, everything is set to 0
	for p in parameters_to_track:
	    self.metrics[p] = [0.0] 
	# pair up coordinates so we have initial and final position for each timestep
	x_s = zip(self.x, self.x[1:])
	y_s = zip(self.y, self.y[1:])
	# object starts still, so initial velocity is zero	
	#self.metrics["v_x"] = [0.0]
	#self.metrics["v_y"] = [0.0]
	#self.metrics["v_net"] =[0.0]
	# initialize a list for everything else
#	for p in ["x_pos", "y_pos", "a_x", "a_y", "distance", "time", "a_net"]:
#	    self.metrics[p] = []
	for n, timestep in enumerate(self.t):
	    # store current (x, y) position 
	    self.metrics["x_pos"].append(x_s[n][0])
 	    self.metrics["y_pos"].append(y_s[n][0])	
	    # x and y velocity is the difference in position divided by the amount of time
	    curr_vx = float(x_s[n][1] - x_s[n][0]) / float(timestep)
	    curr_vy = float(y_s[n][1] - y_s[n][0]) / float(timestep)
	    self.metrics["v_x"].append(curr_vx)
	    self.metrics["v_y"].append(curr_vy)
	    v_net = resultant(curr_vx, curr_vy)
	    self.metrics["v_net"].append(v_net)
	    # x and y acceleration is the difference in velocity divided by the amount of time
	    curr_ax = (curr_vx - self.metrics["v_x"][-2])/timestep
	    curr_ay = (curr_vy - self.metrics["v_y"][-2])/timestep
	    self.metrics["a_x"].append(curr_ax)
	    self.metrics["a_y"].append(curr_ay)
	    a_net = resultant(curr_vx, curr_vy)
	    self.metrics["a_net"].append(a_net)
	    # approximate distance traveled in that timestep
	    # based on average of initial and final velocity in timestep 
	    avg_v = (v_net + self.metrics["v_net"][-2])/2.0
	    self.metrics["distance"].append(avg_v * timestep) 	
	    # amount of time that has passed since last recorded position
	    self.metrics["time"].append(timestep)
	 
    # helper methods for retrieving velocity/acceleration
    # at a given time
    def current_vx(self):
	return self.metrics["v_x"][-1]

    def current_vy(self):
	return self.metrics["v_y"][-1]

    # technically this is speed (always positive)
    def current_v(self):
	return math.sqrt(math.pow(self.current_vx(), 2) + math.pow(self.current_vy(), 2))
 
    def current_ax(self):
	return self.metrics["a_x"][-1]

    def current_ay(self):
	return self.metrics["a_y"][-1]

    def current_a(self):
	return math.sqrt(math.pow(self.current_ax(), 2) + math.pow(self.current_ay(), 2))
    
    # return number of frames
    def num_frames(self):
	return len(self.metrics["time"])

##################################
#     GENERAL HELPER METHODS     #
##################################

# returns (min, max)  of chosen sign (pos, neg, or all by default) values
# for a given field (v_x, x_pos, etc.)
def min_max(vals, which_field, which_vals = "all"):
	# accounts for the initial zero in the vector: position isn't
	# accurate until the first value, velocity until it compares two accurate positions
	# (hence in the second value), and acceleration needs to accurate velocities
	# (hence in the third value)
	offset = 1
	if which_field == "v_x" or which_field == "v_y" or which_field == "v_net":
	    offset = 2
	if which_field == "a_x" or which_field == "a_y" or which_field == "a_net":
	    offset = 3
	candidate_values = vals[offset:]
	max_v = min_v = 0
	if which_vals == "all":
	    max_v = max(candidate_values)
	    min_v = min(candidate_values)
	# treating these as absolute values
	elif which_vals == "neg":
	    neg_vals = filter(lambda x: x <= 0, candidate_values)
	    max_v = min(neg_vals)
	    min_v = max(neg_vals)
	else:
	    pos_vals = filter(lambda x: x > 0, candidate_values)
	    max_v = max(pos_vals)
	    min_v = min(pos_vals)
	return [min_v, max_v]
		
# helper method to find the norm of two vector components
def resultant(x, y):
     return math.sqrt(float(math.pow(x, 2)) + float(math.pow(y, 2)))

# specific to net acceleration
# heuristic: if decelerating in both x and y direction, then 
# net acceleration is negative
def net_accl(x, y):
     num =  math.sqrt(float(math.pow(x, 2)) + float(math.pow(y, 2)))
     if x < 0 and y < 0:
         num *= -1.0
     return num


#################################
#     UI AND MAIN FUNCTIONS     #
#################################
class ObjectTracker(QMainWindow):

    def __init__(self):
	super(ObjectTracker, self).__init__()
        # the crucial part of the tracker is the center buttons
	self.center = QWidget()
	# main layout
	self.layout = QGridLayout()
	# left column of layout
	start_layout = QVBoxLayout()
	# right column of layout
	self.vid_layout = QVBoxLayout()	
	###########################
	# IMPORTANT GLOBAL VALUES #
	###########################
	# ANGLE MEASUREMENT #
	self.found_angle = False
	self.curr_degree = 0
	# hue values for angle measurement
	self.red_hues = [170, 179, "r"]
	self.yellow_hues = [20, 30, "y"]
	self.blue_hues = [80, 120, "b"]
        
	# CAMERA AND DISPLAY #
	# which camera is active
	# (0 is built in, 1 is external USB camera)
	self.camera_index = 0
	# video display size #
	self.fit_camera_width = 480
	self.fit_camera_height = 360
	# initial tracking range (optimized for orange ping-pong ball)
	self.low_color = 2
	self.high_color = 6
        # medium saturation/value (floor/minimum for color intensity in object detection)
        self.MED_SV = 110
        # maximum saturation/value (ceiling/maximum for color intensity in object detection)
        self.MAX_SV = 255
	
	# RECORDING SETTINGS
	self.start_record = False
	self.end_record = False
	# enables UI to run in parallel with video #
	self.busy_updating = False
	self.show_video = False 
	self.video_active = True
	# by default, store all frames
	# change to False to only track position #
	self.full_video_mode = True
	# folder for selecting saved video 
	self.video_folder = ""
        # default folder to store saved video 
	self.output_folder = "Videos"
	
	# INITIAL PLAYBACK SETTINGS #	
	self.playback_speed = 1000
	self.object_color = cv.CV_RGB(0, 255, 0)	
	self.marker_rad = 4
  	self.draw_mode = "circle"

 	# DISTANCE AND COLOR CALIBRATION #	
	self.conversion_factor = 1
	# empirically-determined reasonable value for area of ping-pong ball in pixels
	self.calibration_area = 6650
 	self.mouse_end = False	
	self.mouse_start = False
	
	#################
	# UI COMPONENTS #
	#################
	# laying out UI and connecting it to functionality
	
	# STEP 1: Pick color #	
	first_instruct = QLabel("Step 1: Hold object really close to camera and:")	
	start_layout.addWidget(first_instruct)
	horiz_calib_buttons = QHBoxLayout()
	first_action = QPushButton("Pick color")
        first_action.clicked.connect(self.select_optimal_colors)
	horiz_calib_buttons.addWidget(first_action)
	done_calibrating = QPushButton("Done")
	done_calibrating.clicked.connect(self.stop_record)
 	horiz_calib_buttons.addWidget(done_calibrating)
	start_layout.addLayout(horiz_calib_buttons)		
	
	# STEP 2: Calibrate distance #
	step_2 = QLabel("Step 2: Place object in starting position and:")
	start_layout.addWidget(step_2)
	horiz_act_butt = QHBoxLayout()
	next_action = QPushButton("Calibrate size")
	next_action.clicked.connect(self.calibrate_screen)
	horiz_act_butt.addWidget(next_action)
	do_calibrating = QPushButton("Done")
	do_calibrating.clicked.connect(self.stop_record)
 	horiz_act_butt.addWidget(do_calibrating)
	start_layout.addLayout(horiz_act_butt)		

	# STEP 3: Enter actual size #
        calib_label = QLabel("Step 3: Measure object and: ")
	angle_horiz = QHBoxLayout()
    	calibrate_scale = QPushButton("Enter size")
	calibrate_scale.clicked.connect(self.calibrate)
	angle_horiz.addWidget(calib_label)
	angle_horiz.addWidget(calibrate_scale)
        # measuring angle	
	angle_button = QPushButton("Measure angle")
	angle_button.clicked.connect(self.check_angle)
	start_layout.addLayout(angle_horiz)
	last_horiz = QHBoxLayout()
	self.act_angle = QLabel("0.0 degrees")
	dun = QPushButton("Done")
	dun.clicked.connect(self.found_a)
	last_horiz.addWidget(angle_button)
	last_horiz.addWidget(dun)
 	last_horiz.addWidget(self.act_angle)
	start_layout.addLayout(last_horiz)	

	# STEP 4: Record videos
	record_instruct = QLabel("Step 4: Record videos")
	start_layout.addWidget(record_instruct)
	use_webcam = QPushButton("Start camera")
	use_webcam.clicked.connect(self.track)
	start_layout.addWidget(use_webcam)

	horiz_rec_buttons = QHBoxLayout()
	start_recording = QPushButton("Record!")
	start_recording.clicked.connect(self.record_video)
	horiz_rec_buttons.addWidget(start_recording)
	
	stop_recording = QPushButton("Stop!")
	stop_recording.clicked.connect(self.stop_record)
	horiz_rec_buttons.addWidget(stop_recording)

	save_as = QPushButton("Save video as...")
	save_as.clicked.connect(self.save_file)
	horiz_rec_buttons.addWidget(save_as)
	start_layout.addLayout(horiz_rec_buttons)

	full_color_vid = QCheckBox("Save movement only (not full video)")
        full_color_vid.stateChanged.connect(self.recording_settings)
        start_layout.addWidget(full_color_vid)

	# a note on units #
	unit_instruct = QVBoxLayout()
	unit_ins = QLabel("Values show in meters and seconds")
	unit_instruct.addWidget(unit_ins)	

	# STEP 5: Replay videos #
	vid_label = QLabel("Step 5: Watch videos")
	self.vid_layout.addWidget(vid_label)

	load_vid = QPushButton("Open video")
	load_vid.clicked.connect(self.display_video)
	self.vid_layout.addWidget(load_vid)
	
	quick_buttons = QHBoxLayout()         
	play = QPushButton("Play")
	play.clicked.connect(self.play_video)
	quick_buttons.addWidget(play)	
	pause = QPushButton("Pause")
	pause.clicked.connect(self.pause_video)
	quick_buttons.addWidget(pause)	
	self.vid_layout.addLayout(quick_buttons)
	stop_vid = QPushButton("Done")
	stop_vid.clicked.connect(self.quit_video)
	self.vid_layout.addWidget(stop_vid)

	# playback speed #
        slider_label = QLabel("Adjust video speed below:")
     	self.vid_layout.addWidget(slider_label)
        playback_slider = QSlider(Qt.Horizontal)
        playback_slider.setRange(100, 2000)
        playback_slider.setSliderPosition(1000)
        playback_slider.valueChanged.connect(self.set_playback_speed) 
 	self.vid_layout.addWidget(playback_slider)

	# display options #
	display_options_label = QLabel("Tracking display options:")
	self.vid_layout.addWidget(display_options_label)
	self.display_options = QButtonGroup()
	connect_line = QRadioButton("Continuous line", self)
	circles = QRadioButton("Circle markers", self)
	v_color = QRadioButton("Color by velocity", self)
	a_color = QRadioButton("Color by acceleration", self)
	self.display_options.addButton(connect_line, 1)	
	self.display_options.addButton(circles, 2)
	self.display_options.addButton(v_color, 3)
	self.display_options.addButton(a_color, 4)
	connect_line.clicked.connect(self.set_display_options)
	circles.clicked.connect(self.set_display_options)
	v_color.clicked.connect(self.set_display_options)
	a_color.clicked.connect(self.set_display_options)
	circles.setChecked(True)
	self.vid_layout.addWidget(connect_line)
	self.vid_layout.addWidget(circles)
	self.vid_layout.addWidget(v_color)
	self.vid_layout.addWidget(a_color)
	# object color selection #
	color_label = QLabel("Object color:")
	self.vid_layout.addWidget(color_label)
	self.object_view = QButtonGroup()
	red = QRadioButton("Red", self)
	yellow = QRadioButton("Yellow", self)	
	green = QRadioButton("Green", self)
	blue = QRadioButton("Blue", self)
	self.object_view.addButton(red, 1)
	self.object_view.addButton(yellow, 2)
	self.object_view.addButton(green, 3)
	self.object_view.addButton(blue, 4)
	red.clicked.connect(self.object_display_color)
	yellow.clicked.connect(self.object_display_color)
	green.clicked.connect(self.object_display_color)
	blue.clicked.connect(self.object_display_color)
	# green by default #
	green.setChecked(True)
	self.vid_layout.addWidget(red)	
        self.vid_layout.addWidget(yellow)
	self.vid_layout.addWidget(green)
	self.vid_layout.addWidget(blue)
	# marker size #
	rad_label = QLabel("Adjust marker width below:")
     	self.vid_layout.addWidget(rad_label)
        rad_slider = QSlider(Qt.Horizontal)
        rad_slider.setRange(1, 30)
        rad_slider.setSliderPosition(4)
        rad_slider.valueChanged.connect(self.set_marker_radius) 
 	self.vid_layout.addWidget(rad_slider)

	# switch cameras #	
	external_camera = QPushButton("Switch cameras")
	external_camera.clicked.connect(self.use_external_camera)
	self.vid_layout.addWidget(external_camera)

	# ADVANCED: for calibrating angle measurments #
	top_s = QSlider(Qt.Horizontal)
	top_s.setRange(0, 179)
	top_s.valueChanged.connect(self.top_col)
	bot_s = QSlider(Qt.Horizontal)
	bot_s.setRange(0, 179)
	bot_s.valueChanged.connect(self.bot_col)

	lab = QLabel("Select object color & adjust for angle")
	t = QLabel("Min color:")
	l = QLabel("Max color:")
	self.vid_layout.addWidget(lab)
	self.vid_layout.addWidget(t)
	self.vid_layout.addWidget(bot_s)
	self.vid_layout.addWidget(l)
	self.vid_layout.addWidget(top_s)

	# add all the sub layouts to the main layout
	self.layout.addLayout(start_layout, 0, 0)	
	self.layout.addLayout(self.vid_layout, 0, 1)
	self.layout.addLayout(unit_instruct, 1, 0) 
	self.center.setLayout(self.layout)
	# main window specs #	
	self.setCentralWidget(self.center)
	self.setWindowTitle("Object Tracker")
	self.setGeometry(0, 0, 400, 200)
  
    # when an angle is found #
    def found_a(self):
	self.busy_updating = True
	self.found_angle = True
	self.busy_updating = False
	self.stop_record()

    # distance between two points (x0, y0) and (x1, y1) 
    def dist(self, x0, y0, x1, y1):
	return math.sqrt(math.pow(x1 - x0, 2) + math.pow(y1 - y0, 2))

    # advanced: change settings for angle detection #
    def top_col(self, pos):
	self.busy_updating = True
	if self.object_color == cv.CV_RGB(255, 0, 0):
	    self.red_hues[1] = pos
	elif self.object_color == cv.CV_RGB(255, 255, 0):
	    self.yellow_hues[1] = pos
	elif self.object_color == cv.CV_RGB(0, 0, 255):
	    self.blue_hues[1] = pos
	self.busy_updating = False

    # advanced: change settings for angle detection #
    def bot_col(self, pos):
	self.busy_updating = True
	if self.object_color == cv.CV_RGB(255, 0, 0):
	    self.red_hues[0] = pos
	elif self.object_color == cv.CV_RGB(255, 255, 0):
	    self.yellow_hues[0] = pos
	elif self.object_color == cv.CV_RGB(0, 0, 255):
	    self.blue_hues[0] = pos
	self.busy_updating = False
    
    # implement law of cosines to find angle
    def angle(self, img):
	# extract position of red blue yellow markers
	# find distance between pairs
	# return angle from inverse cosine
	
	imgHSV = cv.CreateImage(cv.GetSize(img), 8, 3)
	cv.CvtColor(img, imgHSV, cv.CV_BGR2HSV)
	cv.NamedWindow("red", cv.CV_WINDOW_AUTOSIZE)
	cv.MoveWindow("red", 800, 0)
	cv.NamedWindow("blue", cv.CV_WINDOW_AUTOSIZE)
	cv.MoveWindow("blue", 800, 100)
	cv.NamedWindow("yellow", cv.CV_WINDOW_AUTOSIZE)
	cv.MoveWindow("yellow", 800, 200)
	
	dot_coords = []
	# use the corresponding thresholds for each color of marker #
	for h_low, h_high, col in [self.red_hues, self.yellow_hues, self.blue_hues]:
	    imgThresh = cv.CreateImage(cv.GetSize(img), 8, 1)
	    cv.InRangeS(imgHSV, cv.Scalar(h_low, 70, 70), cv.Scalar(h_high, 255, 255), imgThresh)
 	    moments = cv.Moments(cv.GetMat(imgThresh))
	    x_mov = cv.GetSpatialMoment(moments, 1, 0)
	    y_mov = cv.GetSpatialMoment(moments, 0, 1)
	    area = cv.GetCentralMoment(moments, 0, 0)
            small_thresh = cv.CreateImage((self.fit_camera_width, self.fit_camera_height), 8, 1)
	    cv.Resize(imgThresh, small_thresh)

	    if col == "r":
		cv.ShowImage("red", small_thresh)
	    elif col == "b":
		cv.ShowImage("blue", small_thresh)
	    elif col == "y":
		cv.ShowImage("yellow", small_thresh) 
	    if area > 0:
		posX = float(x_mov)/float(area)
	    	posY = float(y_mov)/float(area)
	    else:
		posX = 0
		posY = 0
	    dot_coords.append([posX, posY])	 
	
	r = dot_coords[0]
	y = dot_coords[1]
	b = dot_coords[2]
	# get side lengths
	y_r = self.dist(r[0], r[1], y[0], y[1])
	r_b = self.dist(b[0], b[1], r[0], r[1])
	y_b = self.dist(b[0], b[1], y[0], y[1])
	# apply law of cosines
	angle_in_rads = math.pow(y_r, 2) + math.pow(r_b, 2) - math.pow(y_b, 2)
	denom = 2.0 * y_r * r_b
	if denom > 0:
	     angle_in_rads /= 2.0 * y_r * r_b
	else:
	     angle_in_rads = 0
	rads = math.acos(angle_in_rads)
	# convert to degrees
	degs = rads * float(180.0 / math.pi)
	if degs < 0 or degs > 360: 
	     degs = 0
	return degs	

    # wrapper for finding the angle with visual confirmation
    def check_angle(self):
        # in case something else is still open
        cv.DestroyAllWindows()
        capture = cv.CaptureFromCAM(self.camera_index)
        if not capture:
	    QMessageBox.information(self, "Camera Error", "Camera not found")
	    return
	cv.NamedWindow("Video", cv.CV_WINDOW_AUTOSIZE)
    	cv.MoveWindow("Video", 350, 0)
   
        camera_on = True
    	# keep a running average for 100 reads
	total = 0
	num_reads = 0
	while camera_on:
	    if (not self.busy_updating):
		frame = cv.QueryFrame(capture)
		if not frame:
	   	    break	
		deg_found = self.angle(frame)	
		# if an angle is detected, update the running average
		if deg_found != 0:
		    total += deg_found
		    num_reads += 1
		    self.curr_degree = float(total)/float(num_reads)	
		if num_reads > 100:
			self.found_angle = True
		if self.found_angle:	
		    degrees_shown = self.curr_degree
		    degrees_shown = round(degrees_shown, 2)
		    to_text = str(degrees_shown) + " degrees"
		    self.act_angle.setText(to_text)
		
		small_frame = cv.CreateImage((self.fit_camera_width, self.fit_camera_height), 8, 3)
		cv.Resize(frame, small_frame)
		cv.ShowImage("Video", small_frame)	
		k = cv.WaitKey(1)
		
		# press q or escape to quit camera view
		if k == 27 or k == 113 or self.end_record:
		    camera_on = False
		    cv.DestroyAllWindows()
		    self.end_record = False
		    break

    # update marker radius based on slider value
    def set_marker_radius(self, pos):
	self.busy_updating = True
	self.marker_rad = pos
	self.busy_updating = False
 
    # simply switch cameras when button pressed 
    def use_external_camera(self):
	if self.camera_index == 1:
	    self.camera_index = 0
	else:
	    self.camera_index = 1

    # convert pixels/second to user's choice of units/second
    # (meters recommended)
    def to_real_units(self, pixels_per_second):
        return pixels_per_second * self.conversion_factor

    # find dominant hue of selected image
    def histogram(self, src):
	# Convert to HSV
    	hsv = cv.CreateImage(cv.GetSize(src), 8, 3)
    	cv.CvtColor(src, hsv, cv.CV_BGR2HSV)
	h_plane = cv.CreateMat(cv.GetSize(src)[1], cv.GetSize(src)[0], cv.CV_8UC1)
	s_plane = cv.CreateMat(cv.GetSize(src)[1], cv.GetSize(src)[0], cv.CV_8UC1)
	v_plane = cv.CreateMat(cv.GetSize(src)[1], cv.GetSize(src)[0], cv.CV_8UC1)
	cv.Split(hsv, h_plane, s_plane, v_plane, None)
        planes = [h_plane, s_plane]
        h_bins = 30
        s_bins = 32
        hist_size = [h_bins, s_bins]
        # hue varies from 0 (~0 deg red) to 180 (~360 deg red again */
        h_ranges = [0, 180]
        # saturation varies from 0 (black-gray-white) to
        # 255 (pure spectrum color)
        s_ranges = [0, 255]
        ranges = [h_ranges, s_ranges]
        scale = 10
        hist = cv.CreateHist([h_bins, s_bins], cv.CV_HIST_ARRAY, ranges, 1)
        cv.CalcHist([cv.GetImage(i) for i in planes], hist)
	max_val = cv.GetMinMaxHistValue(hist)[3]
	max_hue_bin = max_val[0]
	max_sat_bin = max_val[1]
	
	# display this color in RGB
	h_interval = 6
	s_interval = 8
	hue = h_interval * max_hue_bin
	BGR_color = HSV_to_RGB(hue)
	cv.NamedWindow("About this color?", cv.CV_WINDOW_AUTOSIZE)
        cv.MoveWindow("About this color?", 620, 530)
        color_swatch = cv.CreateImage((200, 140), 8, 3)
        cv.Set(color_swatch, BGR_color)
        cv.ShowImage("About this color?", color_swatch)
	return BGR_color, hue
   
    # update display options # 
    def set_display_options(self):
	self.busy_updating = True
	button_id = self.display_options.checkedId()
	if button_id == 1:
	    self.draw_mode = "line"
	    for b in self.object_view.buttons():
	    	b.setCheckable(True)
	elif button_id == 2:
	    self.draw_mode = "circle"	
	    for b in self.object_view.buttons():
	    	b.setCheckable(True)
	elif button_id == 3:
	    self.draw_mode = "v_path"
	    for b in self.object_view.buttons():
	    	b.setCheckable(False)
	else:
	    self.draw_mode = "a_path"	
	    for b in self.object_view.buttons():
	    	b.setCheckable(False)
	self.busy_updating = False

    # update object color on display #
    def object_display_color(self):
	self.busy_updating = True
	button_id = self.object_view.checkedId()
	if button_id == 1:
 	    self.object_color = cv.CV_RGB(255, 0, 0)
	elif button_id == 2:
	    self.object_color = cv.CV_RGB(255, 255, 0)
	elif button_id == 3:
	    self.object_color = cv.CV_RGB(0, 255, 0)
	else:
	    self.object_color = cv.CV_RGB(0, 0, 255)
	self.busy_updating = False	

    # sets playback speed
    # subtracting from 2100 to make higher slider values
    # correspond intuitively to faster speeds
    def set_playback_speed(self, pos):
        self.playback_speed = 2100 - pos

    # play button
    def play_video(self):
	self.busy_updating = True
	self.show_video = True
	self.busy_updating = False 

    # pause button
    def pause_video(self):
	self.busy_updating = True
	self.show_video = False
	self.busy_updating = False

    # quit button
    def quit_video(self):
        self.busy_updating = True
        self.video_active = False
        self.show_video = False
        self.busy_updating = False
        cv.DestroyAllWindows()

    # start recording button
    def record_video(self):
        self.busy_updating = True
        self.start_record = True
        self.busy_updating = False

    # stop recording/quit video view button
    def stop_record(self):
        self.busy_updating = True
        self.end_record = True
        self.busy_updating = False

    # determines if we're recording every frame, or first frame + subsequent position
    def recording_settings(self):
        if self.full_video_mode:
	    self.full_video_mode = False 
        else:
	    self.full_video_mode = True 

    # "Save as..." (something more memorable) button	
    def save_file(self):
	file_name = QFileDialog.getExistingDirectory()
	if file_name:
	    text = QInputDialog.getText(self, "Save as...", "Enter new file name: ") 
            if text[0] and text[1]:
	        new_name = str(text[0])
                os.rename(file_name, new_name)
	else:
	    QMessageBox.information(self, "File Renaming Error", "No file specified")

    # select directory that contains the trial of interest
    def upload_file(self):
        file_name = QFileDialog.getExistingDirectory()
	if file_name:
	    self.video_folder = file_name    
	    return True
	else:
	    QMessageBox.information(self, "File Load", "No file specified")
	    return False

    # helper function for selecting color threshold
    def update_low_color(self, pos):
        self.busy_updating = True
        self.low_color = pos
        cv.NamedWindow("Start at color", cv.CV_WINDOW_AUTOSIZE)
        cv.MoveWindow("Start at color", 520, 0)
        color_swatch = cv.CreateImage((200, 140), 8, 3)
        cv.Set(color_swatch, HSV_to_RGB(self.low_color))
        cv.ShowImage("Start at color", color_swatch)
	self.busy_updating = False

    # helper function for selecting color threshold
    def update_high_color(self, pos):
        self.busy_updating = True
        self.high_color = pos
        cv.NamedWindow("End at color", cv.CV_WINDOW_AUTOSIZE)
        cv.MoveWindow("End at color", 750, 0)
        color_swatch = cv.CreateImage((200, 140), 8, 3)
        cv.Set(color_swatch, HSV_to_RGB(self.high_color))
        cv.ShowImage("End at color", color_swatch)
	self.busy_updating = False
 
    ################################
    # MAIN VIDEO PLAYBACK FUNCTION #
    ################################
    def display_video(self):
        if not self.upload_file():
	    return
        self.video_active = True
    	# hand-tuned, apologies
	cv.NamedWindow("Velocity", cv.CV_WINDOW_AUTOSIZE)
        cv.MoveWindow("Velocity", 0, 590)   
        cv.NamedWindow("Acceleration", cv.CV_WINDOW_AUTOSIZE)
        cv.MoveWindow("Acceleration", 415, 590)
        cv.NamedWindow("Replay", cv.CV_WINDOW_AUTOSIZE) 
        cv.MoveWindow("Replay", 610, 20)
        cv.NamedWindow("Overall", cv.CV_WINDOW_AUTOSIZE)
        cv.MoveWindow("Overall", 880, 590)

        # load background
        input_background = str(self.video_folder) + "/background.png"
	background = cv.LoadImage(input_background)
	if not background: 
	    QMessageBox.information(self, "Open video", "No such video")  
   	    return	
        cv.ShowImage("Replay", background)
   	size = cv.GetSize(background)
	screen_width = size[0]
	screen_height = size[1] 
        
	# load position data
        input_data = str(self.video_folder) + "/Data"
        f_in = open(input_data, 'r')
	data = pickle.load(f_in)
	f_in.close()
	if not data:
	    QMessageBox.information(self, "Loading video", "Unable to load data")
        # Data knows it's a Speed object.
	# this is why Python ROCKS.
	num_frames = data.num_frames()
 
	top_speed = 0
	dist = 0.0
        # getting images
	imgArr = []
        img_name = str(self.video_folder) + "/frame_"
	
	# if we saved the full video (as opposed to just the position info)
        if self.full_video_mode:
 	    for frame in range(1, num_frames):
		full_img = str(img_name) + str(frame) + ".png"
		img = cv.LoadImage(full_img)
		imgArr.append(img)
        font = cv.InitFont(cv.CV_FONT_HERSHEY_SIMPLEX, 1.0, 1.0, 0, 1, cv.CV_AA)
	# all parameters we want to track
        params = ["x_pos", "y_pos", "v_x", "v_y", "a_x", "a_y", "distance", "v_net", "a_net"]
        # values for which we want to scale display color with relative magnitude
	fields = ["v_x", "v_y", "a_x", "a_y", "v_net", "a_net"]

        # for velocity and acceleration, there is min max for pos and neg
        # returns (min, max)
        neg_outliers = {}
	pos_outliers = {}
	pos_color = cv.CV_RGB(0, 255, 0) # green
        neg_color = cv.CV_RGB(255, 0, 0) # red
    
	for f in fields:
	    if f is not "v_net" and f is not "a_net":
	    	neg_outliers[f] = min_max(data.metrics[f], f, which_vals = "neg")
	    pos_outliers[f] = min_max(data.metrics[f], f, which_vals = "pos")

        next_image = cv.CloneImage(background)
	# ignore the first values for everything
	# (since velocity/acceleration will not be accurate)
	img_index = 1

	line_list = []
	color_list = []
        while not self.busy_updating and self.video_active:
	    # enables pause button functionality
	    if not self.video_active:
	        break
	    qr = cv.WaitKey(10)
  	    # if we're done with the video
	    if img_index >= num_frames:
	        break
	    	    	   
            if self.show_video:
	      # loop around when video done
	      if img_index == num_frames - 1:
	  	   img_index = 0
		   dist = 0.0
		   top_speed = 0.0
		   line_list = []
		   color_list = []
	      if img_index < num_frames -1:
		# advance to next image
	        if self.full_video_mode: 
	            next_image = imgArr[img_index]
		# values are one ahead of the frames
	        img_index += 1
		# make white canvases for writing values
    	        speed_img = cv.CreateImage((400, 140), 8, 3)
	        cv.Set(speed_img, cv.CV_RGB(255, 255, 255))
	        accl_img = cv.CreateImage((450, 140), 8, 3)
	        cv.Set(accl_img, cv.CV_RGB(255, 255, 255))
	        overall_img = cv.CreateImage((390, 140), 8, 3)
	        cv.Set(overall_img, cv.CV_RGB(255, 255, 255))

                x_coord = data.metrics["x_pos"][img_index]
	        y_coord = data.metrics["y_pos"][img_index]
	        data_for_step = []
		# the below will eventually be [v_net, a_net, v_x, v_y, a_x, a_y]
   	        colors_for_step = []
	        # convert all data to real units
	        # and determine red/green display color
	        for p in params:
		    raw_pixel_val = data.metrics[p][img_index]
		    val = self.to_real_units(raw_pixel_val)
		    if val < 0:
		        if p == "x_pos" or p == "y_pos" or p == "distance":
			    colors_for_step.append(neg_color)
		        else:
			    colors_for_step.append(scale_color(raw_pixel_val, neg_outliers[p][0], neg_outliers[p][1], "R"))
		    else:
		        if p == "x_pos" or p == "y_pos" or p == "distance":
			    colors_for_step.append(pos_color)
		        else:	    
			    colors_for_step.append(scale_color(raw_pixel_val, pos_outliers[p][0], pos_outliers[p][1], "G"))
		    data_for_step.append(val)		
	   
	       # track top speed after first three steps (since these are less precise)
		v_net = data_for_step[7]
	        if abs(v_net) > abs(top_speed) and img_index > 3:
	 	    top_speed = v_net
	
	        # display all velocities/accelerations
	        x_speed = "Horizontal: " +  str(round(data_for_step[2], 1))
	        y_speed = "Vertical: " + str(round(data_for_step[3], 1))
	        total_speed = "Net: " + str(round(data_for_step[7], 1))
	        x_accl = "Horizontal: " +  str(round(data_for_step[4], 1))
	        y_accl = "Vertical: " + str(round(data_for_step[5], 1))
	        total_accl = "Net: " + str(round(data_for_step[8], 1))  
	        if img_index > 1:
	    	    dist += data_for_step[6]
	        dist_traveled = "Distance: " + str(round(dist, 1))
	        top_speed_so_far = "Top speed: " + str(round(top_speed, 1))   

	        # add to speed window
	        cv.PutText(speed_img, x_speed, (10, 40), font, colors_for_step[2]) 
	        cv.PutText(speed_img, y_speed, (10, 80), font, colors_for_step[3]) 
	        cv.PutText(speed_img, total_speed, (10, 120), font, colors_for_step[7]) 
	        # add to accl window
	        cv.PutText(accl_img, x_accl, (10, 40), font, colors_for_step[4])
	        cv.PutText(accl_img, y_accl, (10, 80), font, colors_for_step[5])
	        cv.PutText(accl_img, total_accl, (10, 120), font, colors_for_step[8])
	        # add to overall window
	        cv.PutText(overall_img, dist_traveled, (10, 60), font, cv.Scalar(0, 255, 0))
	        cv.PutText(overall_img, top_speed_so_far, (10, 120), font, cv.Scalar(0, 255, 0))
	        # if the object fits on the screen, display it as a green circle 
	        if x_coord < screen_width and y_coord < screen_height:
		    if self.draw_mode == "circle":
			cv.Circle(next_image, (int(x_coord), int(y_coord)), self.marker_rad, self.object_color, thickness = -1)
		    elif self.draw_mode == "line":
			if img_index > 1:
			    x_0 = data.metrics["x_pos"][img_index - 1]
			    y_0 = data.metrics["y_pos"][img_index - 1]
			    line_list.append([int(x_0), int(y_0), int(x_coord), int(y_coord)])
		   	    for l in line_list:
				cv.Line(next_image, (l[0], l[1]), (l[2], l[3]), self.object_color, thickness = self.marker_rad)
		    elif self.draw_mode == "v_path":
			# v-dependent path #
			### colors for step at 7 ###
		    	if img_index > 1:
			    x_0 = data.metrics["x_pos"][img_index - 1]
			    y_0 = data.metrics["y_pos"][img_index - 1]
			    line_list.append([int(x_0), int(y_0), int(x_coord), int(y_coord)])
			    color_list.append(colors_for_step[7])
		   	    for index, l in enumerate(line_list):
				cv.Line(next_image, (l[0], l[1]), (l[2], l[3]), color_list[index], thickness = self.marker_rad)
		    else:
			# a-dependent path
			### colors for step at 8 ###
		    	if img_index > 1:
			    x_0 = data.metrics["x_pos"][img_index - 1]
			    y_0 = data.metrics["y_pos"][img_index - 1]
			    line_list.append([int(x_0), int(y_0), int(x_coord), int(y_coord)])
			    color_list.append(colors_for_step[8])
		   	    for index, l in enumerate(line_list):
				cv.Line(next_image, (l[0], l[1]), (l[2], l[3]), color_list[index], thickness = self.marker_rad)
		    cv.ShowImage("Replay", next_image)
		    cv.ShowImage("Velocity", speed_img)
		    cv.ShowImage("Acceleration", accl_img)
		    cv.ShowImage("Overall", overall_img)
	   	    k = cv.WaitKey(self.playback_speed)
		    # press q or escape to quit
		    if k == 113 or k == 27:
		        self.show_video = False
			cv.DestroyAllWindows()
		        break
        self.show_video = False 
      
    # allows user to calibrate pixel to actual distance ratio
    # by simply holding up an object of known area (that is
    # later entered into the program) at the relevant distance
    # away from the camera
    # takes the maximum area over the time the video is active
    def calibrate_screen(self):
        # in case something else is still open
        cv.DestroyAllWindows()
        capture = cv.CaptureFromCAM(self.camera_index)
        if not capture:
	    QMessageBox.information(self, "Camera Error", "Camera not found")
    	    return
	cv.NamedWindow("hold up object at preferred distance from camera", cv.CV_WINDOW_AUTOSIZE)
        cv.NamedWindow("select for max visibility", cv.CV_WINDOW_AUTOSIZE)
        cv.MoveWindow("hold up object at preferred distance from camera", 320, 0) 
        cv.MoveWindow("select for max visibility", 800, 82)
        cv.CreateTrackbar("Start at color", "hold up object at preferred distance from camera", self.low_color, 179, self.update_low_color)
        cv.CreateTrackbar("End at color", "hold up object at preferred distance from camera", self.high_color, 179, self.update_high_color)
        camera_on = True
        while camera_on:
	    if (not self.busy_updating):
		frame = cv.QueryFrame(capture)
		if not frame:
	    		break
		# convert color to hue space for easier tracking
		imgHSV = cv.CreateImage(cv.GetSize(frame), 8, 3)
		cv.CvtColor(frame, imgHSV, cv.CV_BGR2HSV)
		imgThresh = cv.CreateImage(cv.GetSize(frame), 8, 1)
		# interactive thresholding
		cv.InRangeS(imgHSV, cv.Scalar(self.low_color, self.MED_SV, self.MED_SV), cv.Scalar(self.high_color, self.MAX_SV, self.MAX_SV), imgThresh)
  	
		moments = cv.Moments(cv.GetMat(imgThresh))
		self.calibration_area = cv.GetCentralMoment(moments, 0, 0)
		# shrink images for display
		small_thresh = cv.CreateImage((self.fit_camera_width, self.fit_camera_height), 8, 1)
		cv.Resize(imgThresh, small_thresh)
		small_frame = cv.CreateImage((self.fit_camera_width, self.fit_camera_height), 8, 3)
		cv.Resize(frame, small_frame)
		cv.ShowImage("hold up object at preferred distance from camera", small_frame)
		cv.ShowImage("select for max visibility", small_thresh)

		k = cv.WaitKey(1)
		# press q or escape to quit camera view
		if k == 27 or k == 113 or self.end_record:
		    camera_on = False
		    cv.DestroyAllWindows()
		    self.end_record = False
		    break

    # sets the conversion factor to actual units/pixels (currently meters/pixel)
    def calibrate(self):
	new_diameter = QInputDialog.getDouble(self, "Object size", "Enter object diameter in centimeters:", minValue = 1, maxValue = 20, decimals = 2)	
	if new_diameter[0] and new_diameter[1]:
	    val = new_diameter[0]
	    # val is the diameter of the actual ball in cm
	    radius_in_pixels = math.sqrt(float(self.calibration_area)/ math.pi)
	    radius_in_m = float(int(val))/200.0
	    self.conversion_factor = float(radius_in_m)/float(radius_in_pixels)
	else:
	    QMessageBox.information(self, "Measurement Input Error", "Please enter a number")
    
    #################################
    # MAIN OBJECT TRACKING FUNCTION #
    #################################
    def track(self):
        # in case something else is still open
        cv.DestroyAllWindows()
        tracker = Speed()
    	imgArr = []
        capture = cv.CaptureFromCAM(self.camera_index)
        if not capture:
	    QMessageBox.information(self, "Camera Error", "Camera not found")
	    return
	cv.NamedWindow("Video", cv.CV_WINDOW_AUTOSIZE)
    	cv.MoveWindow("Video", 320, 0)
    	cv.NamedWindow("Tracking", cv.CV_WINDOW_AUTOSIZE)
    	cv.MoveWindow("Tracking", 800, 82)
    	moments = 0
    	cv.CreateTrackbar("Start at color", "Video", self.low_color, 179, self.update_low_color)
    	cv.CreateTrackbar("End at color", "Video", self.high_color, 179, self.update_high_color)
    
	start_time = 0   
        camera_on = True
        tracking = False
	needs_saving = False
	background = 0
        while camera_on:
	    if (not self.busy_updating):
		frame = cv.QueryFrame(capture)
		if not frame:
	   	    break	
		#convert color to hue space for easier tracking
		imgHSV = cv.CreateImage(cv.GetSize(frame), 8, 3)
	 	cv.CvtColor(frame, imgHSV, cv.CV_BGR2HSV)
		imgThresh = cv.CreateImage(cv.GetSize(frame), 8, 1)
		# implement interactive thresholding
		cv.InRangeS(imgHSV, cv.Scalar(self.low_color, self.MED_SV, self.MED_SV), cv.Scalar(self.high_color, self.MAX_SV, self.MAX_SV), imgThresh)
 		 		
		# find image momentsm, compute object position 
		# by dividing by area
		moments = cv.Moments(cv.GetMat(imgThresh))
		x_mov = cv.GetSpatialMoment(moments, 1, 0)
		y_mov = cv.GetSpatialMoment(moments, 0, 1)
		area = cv.GetCentralMoment(moments, 0, 0)
		# size is 480 360 for webcam
		# 324, 243 for massive-imaged external camera
		small_thresh = cv.CreateImage((self.fit_camera_width, self.fit_camera_height), 8, 1)
		cv.Resize(imgThresh, small_thresh)
		small_frame = cv.CreateImage((self.fit_camera_width, self.fit_camera_height), 8, 3)
		cv.Resize(frame, small_frame)
		cv.ShowImage("Tracking", small_thresh)	
		cv.ShowImage("Video", small_frame)

 		k = cv.WaitKey(1)
			
		# press q or escape to quit camera view
		if k == 27 or k == 113:
		    camera_on = False
		    tracking = False
		    cv.DestroyAllWindows()
		    break; 

		# click "Record!" or  press "g" to start tracking speed/recording 	
		elif k == 103 or self.start_record:
		    needs_saving = True
		    start_time = time.clock()
		    tracking = True
		    # store background in memory and proceed to recording
		    background = cv.CloneImage(frame)
		    tracker.start_time = start_time
 		    self.start_record = False
		    imgArr.append(background)
		# click "Stop recording" or press "d" to stop tracking speed/recording
		# save everything in the proper format and close recording windows
		elif k == 100 or self.end_record:
		  if needs_saving:
		    tracking = False
		    tracker.stop_time = time.clock()
		    curr_dir = os.listdir(".")
		    # create the output folder if it doesn't already exist
		    if self.output_folder not in curr_dir:
		        path_var = "./" + str(self.output_folder)
			os.mkdir(path_var)
		    # default saving directory is output_folder/Trial_<start time of trial>
		    new_vid_folder =  "./" + str(self.output_folder) + "/Trial_" + str(start_time)
		    os.mkdir(new_vid_folder)
		    tracker.out_folder = new_vid_folder 
		    # save the first frame of the film as the background image
		    background_name = str(tracker.out_folder) + "/background.png"
	   	    cv.SaveImage(background_name, background)	
 		    index = 0
		    for img in imgArr:
			output_name = str(tracker.out_folder) + "/frame_" + str(index) + ".png"
			cv.SaveImage(output_name, img)			
	    	   	index += 1 
		   # compute velocity and acceleration values	
		    tracker.update()
		    # save the tracking done so far (by pickling)
		    # can later be exported as a text file
		    tracker_file = str(tracker.out_folder) + "/Data"
		    f = open(tracker_file, 'w')
		    pickle.dump(tracker, f)
		    f.close()
		    cv.DestroyAllWindows()		    
		    break
		  else:
		    cv.DestroyAllWindows()
		    break
		if tracking:
		    # store object position
		    if area > 0:
			posX = float(x_mov)/float(area)
			posY = float(y_mov)/float(area)
			curr_time = time.clock()
		       	tracker.add_pos(posX, posY, curr_time - start_time)
			start_time = curr_time 			
			imgArr.append(cv.CloneImage(frame))

    # mouse function for click & select
    # in color calibration
    def mouseHandler(self, event, x, y, flags, param):
	hue_shift = 5
	if event == cv.CV_EVENT_LBUTTONDOWN:
	    self.mouse_start = [x, y]
	elif event == cv.CV_EVENT_MOUSEMOVE:
	    if self.mouse_start:
	        img_with_rect = cv.CloneImage(self.frame)
	        cv.Rectangle(img_with_rect, (self.mouse_start[0], self.mouse_start[1]), (x, y), cv.Scalar(0, 255, 0), 2, 8, 0) 
	        cv.ShowImage("click & drag to select object", img_with_rect)	
	elif event == cv.CV_EVENT_LBUTTONUP:
	    img_with_rect = cv.CloneImage(self.frame)
	    cv.Rectangle(img_with_rect, (self.mouse_start[0], self.mouse_start[1]), (x, y), cv.Scalar(0, 255, 0), 2, 8, 0) 
	    cv.ShowImage("click & drag to select object", img_with_rect)
	    best_color, hue = self.histogram(self.frame)
	    self.low_color = max(0, hue - hue_shift) 
	    self.high_color = min(179, hue + hue_shift)
	    self.mouse_start = False

    # main function for returning optimal color automatically
    def select_optimal_colors(self):
        # in case something else is still open
        cv.DestroyAllWindows()
        capture = cv.CaptureFromCAM(self.camera_index)
        if not capture:
	    QMessageBox.information(self, "Camera Error", "Camera not found")
    	    return
	cv.NamedWindow("click & drag to select object", cv.CV_WINDOW_AUTOSIZE)	
        cv.MoveWindow("click & drag to select object", 610, 0) 
       	cv.SetMouseCallback("click & drag to select object", self.mouseHandler, None) 
        camera_on = True
        while camera_on:
	    if (not self.busy_updating):
		frame = cv.QueryFrame(capture)
		if not frame:
	    		break
		cv.ShowImage("click & drag to select object", frame)
		self.frame = frame
		k = cv.WaitKey(1)
		# press q or escape to quit camera view
		if k == 27 or k == 113 or self.end_record:
		    camera_on = False
		    cv.DestroyAllWindows()
		    self.end_record = False
		    break

# add vectors to the image	
# input: position as tuple, magnitude as pixel tuple
# may still need to scale since it's velocity (to start)
def draw_vector(image, position, color, magnitude, max_param):
    scaled_mag = [0, 0]
    for dim in [0, 1]:
	if magnitude[dim] > 0:
    		space_left = image.size[dim] - position[dim]
	else:
		space_left = position[dim]
        scaled_mag[dim] = int(space_left * (float(magnitude[dim]) / float(max_param[dim])))
    end_pt = cv.Point(position[0] + scaled_mag[0], position[1] + scaled_mag[1])    
    cv.Line(image, position, end_pt, (0, 255, 0), thickness = self.marker_rad)
    return image     

####################################
# MAIN: THIS MAKES EVERYTHING WORK #
####################################
def main():
    app = QApplication(sys.argv)
    objectTracker = ObjectTracker()
    objectTracker.show()
    sys.exit(app.exec_())

# convert HSV to RGB since OpenCV can't do this #
def HSV_to_RGB(hue_part):
    hue = hue_part * 2
    R = G = B = 0
    if hue < 60:
	R = 255
	G = int(255 * float(hue)/float(60))
    elif hue < 120:
    	R = int(255 * float(120 - hue)/float(60))
    	G = 255
    elif hue < 180:
	G = 255
	B = int(255 * float(hue - 120)/float(60))
    elif hue < 240:
	G = int(255 * float(240 - hue)/float(60))
	B = 255
    elif  hue < 300:	
	R = int(255 * float(hue - 240)/float(60))
	B = 255
    else:
	R = 255
	B = int(255 * float(360 - hue)/float(60))
    return cv.Scalar(B, G, R)

# max value should be max brightness, min value should be min brightness, etc.
# val/val range = text_color/color_range
def scale_color(val, min_, max_, color):
    min_red = 120
    red_interval = 125
    green_interval = 205
    min_green = 50
    val_offset = abs(val - min_) 
    if val_offset > max_:
	val_offset = max_ 
    val_ratio = float(val_offset)/float((abs(max_ - min_)))
    if val_ratio < 0:
	val_ratio = 0
    elif val_ratio > 1:
	val_ratio = 1
    if color == "R":
    	scaled = min_red + int(val_ratio * float(red_interval))    
   	return cv.CV_RGB(min(scaled, 255), 0, 0)
    else:
	scaled = min_green + int(val_ratio * float(green_interval))     
	return cv.CV_RGB(0, min(scaled, 255), 0)    

if __name__ == '__main__':
    main()

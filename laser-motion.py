# import the necessary packages
from imutils.video import VideoStream
import argparse
import datetime
import imutils
import time
import cv2
#GPIO stuff
import RPi.GPIO as GPIO
#Math
import math
import os

##Motor Interface Component
pitch_pwm = None
yaw_pwm = None

pitch_port = 8
laser_port = 10
yaw_port = 12
frames_back_check = 90

circle = 0
RADIUS = 100
SPEED = 0.5
THRESHOLD = 100

VIDEO = True

def init_gpio_config():
    print("Begin GPIO init")
    global pitch_pwm
    global yaw_pwm
    
    GPIO.setmode(GPIO.BOARD)
    GPIO.setup(pitch_port, GPIO.OUT)
    GPIO.setup(yaw_port, GPIO.OUT)
    GPIO.setup(laser_port, GPIO.OUT)
    print("Ports set, starting PWM")
    pitch_pwm = GPIO.PWM(pitch_port, 50)
    yaw_pwm = GPIO.PWM(yaw_port, 50)
    pitch_pwm.start(0)
    yaw_pwm.start(0)
    print("PWM started")

def cleanup_gpio_config():
    print("Cleaning up gpio")
    set_laser(False)
    pitch_pwm.ChangeDutyCycle(6)
    yaw_pwm.ChangeDutyCycle(6)
    print("Returning motors to centre")
    time.sleep(2)
    print("Stopping PWM and shutting down")
    pitch_pwm.stop()
    yaw_pwm.stop()
    GPIO.cleanup()
    print("GPIO shutdown")

def set_laser(on):
    if on:
        GPIO.output(laser_port, GPIO.HIGH)
    else:
        GPIO.output(laser_port, GPIO.LOW)

def limit(delta, lower, upper):
    if delta < lower:
        return lower
    elif delta > upper:
        return upper
    else:
        return delta

def set_position_by_percent(motor_pwm, percent, lim_b, lim_t):
    cycle = 2.0 + (percent * 10.0)
    cycle = limit(cycle, lim_b, lim_t)
    #if VIDEO:
    #    print("Setting duty cycle to percent", percent, "Which yields cycle", cycle)
    motor_pwm.ChangeDutyCycle(cycle)

def set_target(scn_x, scn_y):
    offset_x = RADIUS * math.sin(math.degrees(circle))
    offset_y = RADIUS * math.cos(math.degrees(circle))
    
    inv_x = 500-scn_x+offset_x
    
    x_pct = inv_x/500
    xc_pct = 0.220 + (0.361 * x_pct)
    y_pct = (scn_y+offset_y)/375
    yc_pct = 0.220 + (0.234 * y_pct)
    
    
    
    set_position_by_percent(pitch_pwm, xc_pct, 2.5, 11.5)
    set_position_by_percent(yaw_pwm, yc_pct, 2.5, 11.5)

def get_mouse(event, x, y, flags, params):
    #set_target(x, y)
    pass

##Motion detection component
# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-v", "--video", help="path to the video file")
ap.add_argument("-a", "--min-area", type=int, default=300, help="minimum area size")
ap.add_argument("-n", "--no-display", help="If present display is disabled.")
args = vars(ap.parse_args())

# if the video argument is None, then we are reading from webcam
if args.get("video", None) is None:
    vs = VideoStream(src=0).start()
    time.sleep(2.0)

# otherwise, we are reading from a video file
else:
    vs = cv2.VideoCapture(args["video"])

init_gpio_config()
set_laser(True)

VIDEO = False

print("Waiting for GPIO activation")
time.sleep(0.5)

# initialize the first frame in the video stream
#firstFrame = None
frameBuf = []
if VIDEO:
    cv2.namedWindow('Security Feed')
    cv2.setMouseCallback('Security Feed', get_mouse)
print("OS Working dir " + os.getcwd())
try:
    print("Entering main loop")
    # loop over the frames of the video
    frameNum = 0
    while True:
        #Makes it draw a circle
        frameNum += 1
        circle += SPEED
        if circle >= 360:
            circle = 0
        
        # grab the current frame and initialize the occupied/unoccupied
        # text
        frame = vs.read()
        frame = frame if args.get("video", None) is None else frame[1]
        text = "Unoccupied"
        
        # if the frame could not be grabbed, then we have reached the end
        # of the video
        if frame is None:
            break
        
        # resize the frame, convert it to grayscale, and blur it
        frame = imutils.resize(frame, width=500)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)
        
        # if the first frame is None, initialize it
        #if firstFrame is None:
        #    firstFrame = gray
        #    continue
        
        #print("Typeof gray", type(gray), "dims", gray.shape)
        
        frameBuf.append(gray)
        if len(frameBuf) > frames_back_check:
            del frameBuf[0]
        
        # compute the absolute difference between the current frame and
        # first frame
        frameDelta = cv2.absdiff(frameBuf[0], gray)
        thresh = cv2.threshold(frameDelta, THRESHOLD, 255, cv2.THRESH_BINARY)[1]
        
        # dilate the thresholded image to fill in holes, then find contours
        # on thresholded image
        thresh = cv2.dilate(thresh, None, iterations=2)
        cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE)
        cnts = imutils.grab_contours(cnts)
        
        target_this_frame = False
        
        # loop over the contours
        for c in cnts:
            # if the contour is too small, ignore it
            if cv2.contourArea(c) < args["min_area"]:
                continue

            # compute the bounding box for the contour, draw it on the frame,
            # and update the text
            (x, y, w, h) = cv2.boundingRect(c)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            
            if target_this_frame == False:
                set_target(x + w/2, y + h/2)
                target_this_frame = True
            
            text = "Occupied"

        if text == "Occupied":
            set_laser(True)
        else:
            set_laser(False)
            pitch_pwm.ChangeDutyCycle(0)
            yaw_pwm.ChangeDutyCycle(0)
        
        # draw the text and timestamp on the frame
        cv2.putText(frame, "Room Status: {}".format(text), (10, 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
        cv2.putText(frame, datetime.datetime.now().strftime("%A %d %B %Y %I:%M:%S%p"),
            (10, frame.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

        # show the frame and record if the user presses a key
        cv2.imshow("Security Feed", frame)
        cv2.imshow("Thresh", thresh)
        cv2.imshow("Frame Delta", frameDelta)
        
        key = cv2.waitKey(1) & 0xFF

        # if the `q` key is pressed, break from the lop
        if key == ord("q"):
            print("Requested break causing cleanup")
            break

except KeyboardInterrupt:
    print("Interrupt causing cleanup")
# cleanup the camera and close any open windows
print("Releasing CV2")
vs.stop() if args.get("video", None) is None else vs.release()
cleanup_gpio_config()
print("Closing all windows")
cv2.destroyAllWindows()
print("Stopped")

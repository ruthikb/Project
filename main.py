import time
import argparse

import cv2
import dlib
import numpy as np

from Utils import get_face_area
from Eye_Dector_Module import EyeDetector as EyeDet
from Pose_Estimation_Module import HeadPoseEstimator as HeadPoseEst
from Attention_Scorer_Module import AttentionScorer as AttScorer
import sqlite3
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Set up the Chrome WebDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# Open Google Meet or any URL to start with
driver.get('https://meet.google.com/')
# camera matrix obtained from the camera calibration script, using a 9x6 chessboard
camera_matrix = np.array(
    [[899.12150372, 0., 644.26261492],
     [0., 899.45280671, 372.28009436],
     [0, 0,  1]], dtype="double")

DATABASE = 'database.db'
# distortion coefficients obtained from the camera calibration script, using a 9x6 chessboard
dist_coeffs = np.array(
    [[-0.03792548, 0.09233237, 0.00419088, 0.00317323, -0.15804257]], dtype="double")

# Helper function to log activity
def log_activity(user_id, activity):
    print("writing database")
    with sqlite3.connect(DATABASE) as conn:
        print("successfull")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO activity_log (user_id, activity) VALUES (?, ?)", (user_id, activity))
        conn.commit()



def main():
    a=0
    b=0
    c=0
    d=0

    parser = argparse.ArgumentParser(description='Driver State Detection')

    # selection the camera number, default is 0 (webcam)
    parser.add_argument('-c', '--camera', type=int,
                        default=0, metavar='', help='Camera number, default is 0 (webcam)')

    # selection of fps limit for computing time between frames
    parser.add_argument('-F', '--fps_limit', type=int, default=11, metavar='',
                        help='FPS limit, default is 11 (WARNING: if this surpasses the fps max rate reachable by your device, it will cause problems for the scores computation')

    # TODO: add option for choose if use camera matrix and dist coeffs

    # visualisation parameters
    parser.add_argument('--show_fps', type=bool, default=True,
                        metavar='', help='Show the actual FPS of the capture stream, default is true')
    parser.add_argument('--show_proc_time', type=bool, default=True,
                        metavar='', help='Show the processing time for a single frame, default is true')
    parser.add_argument('--show_eye_proc', type=bool, default=False,
                        metavar='', help='Show the eyes processing, deafult is false')
    parser.add_argument('--show_axis', type=bool, default=True,
                        metavar='', help='Show the head pose axis, default is true')
    parser.add_argument('--verbose', type=bool, default=False,
                        metavar='', help='Prints additional info, default is false')

    # Attention Scorer parameters (EAR, Gaze Score, Pose)
    parser.add_argument('--smooth_factor', type=float, default=0.5,
                        metavar='', help='Sets the smooth factor for the head pose estimation keypoint smoothing, default is 0.5')
    parser.add_argument('--ear_tresh', type=float, default=0.15,
                        metavar='', help='Sets the EAR threshold for the Attention Scorer, default is 0.15')
    parser.add_argument('--ear_time_tresh', type=float, default=2,
                        metavar='', help='Sets the EAR time (seconds) threshold for the Attention Scorer, default is 2 seconds')
    parser.add_argument('--gaze_tresh', type=float, default=0.2,
                        metavar='', help='Sets the Gaze Score threshold for the Attention Scorer, default is 0.2')
    parser.add_argument('--gaze_time_tresh', type=float, default=2, metavar='',
                        help='Sets the Gaze Score time (seconds) threshold for the Attention Scorer, default is 2 seconds')
    parser.add_argument('--pitch_tresh', type=float, default=30,
                        metavar='', help='Sets the PITCH threshold (degrees) for the Attention Scorer, default is 30 degrees')
    parser.add_argument('--yaw_tresh', type=float, default=20,
                        metavar='', help='Sets the YAW threshold (degrees) for the Attention Scorer, default is 20 degrees')
    parser.add_argument('--roll_tresh', type=float, default=30,
                        metavar='', help='Sets the ROLL threshold (degrees) for the Attention Scorer, default is 30 degrees')
    parser.add_argument('--pose_time_tresh', type=float, default=2.5,
                        metavar='', help='Sets the Pose time threshold (seconds) for the Attention Scorer, default is 2.5 seconds')

    # parse the arguments and store them in the args variable dictionary
    args = parser.parse_args()

    if args.verbose:
        print(f"Arguments and Parameters used:\n{args}\n")

    if not cv2.useOptimized():
        try:
            cv2.setUseOptimized(True)  # set OpenCV optimization to True
        except:
            print(
                "OpenCV optimization could not be set to True, the script may be slower than expected")

    ctime = 0  # current time (used to compute FPS)
    ptime = 0  # past time (used to compute FPS)
    prev_time = 0  # previous time variable, used to set the FPS limit
    # FPS upper limit value, needed for estimating the time for each frame and increasing performances
    fps_lim = args.fps_limit
    time_lim = 1. / fps_lim  # time window for each frame taken by the webcam

    # previous landmarks for head pose estimation (initially set to None) (used for smoothing)
    prev_landmarks = None

    # instantiation of the dlib face detector object
    Detector = dlib.get_frontal_face_detector()
    Predictor = dlib.shape_predictor(
        "predictor/shape_predictor_68_face_landmarks.dat")  # instantiation of the dlib keypoint detector model
 
    # instantiation of the eye detector and pose estimator objects
    Eye_det = EyeDet(show_processing=args.show_eye_proc)

    Head_pose = HeadPoseEst(show_axis=args.show_axis)

    # instantiation of the attention scorer object, with the various thresholds
    # NOTE: set verbose to True for additional printed information about the scores
    Scorer = AttScorer(fps_lim, ear_tresh=args.ear_tresh, ear_time_tresh=args.ear_time_tresh, gaze_tresh=args.gaze_tresh,
                       gaze_time_tresh=args.gaze_time_tresh, pitch_tresh=args.pitch_tresh, yaw_tresh=args.yaw_tresh,
                       roll_tresh=args.roll_tresh, pose_time_tresh=args.pose_time_tresh, verbose=args.verbose)

    # capture the input from the default system camera (camera number 0)
    cap = cv2.VideoCapture(args.camera)
    if not cap.isOpened():  # if the camera can't be opened exit the program
        print("Cannot open camera")
        exit()

    while True:  # infinite loop for webcam video capture

        delta_time = time.perf_counter() - prev_time  # delta time for FPS capping
        ret, frame = cap.read()  # read a frame from the webcam

        if not ret:  # if a frame can't be read, exit the program
            print("Can't receive frame from camera/stream end")
            break

         # if the frame comes from webcam, flip it so it looks like a mirror.
        if args.camera == 0:
            frame = cv2.flip(frame, 2)

        if delta_time >= time_lim:  # if the time passed is bigger or equal than the frame time, process the frame
            prev_time = time.perf_counter()

            # compute the actual frame rate per second (FPS) of the webcam video capture stream, and show it
            ctime = time.perf_counter()
            fps = 1.0 / float(ctime - ptime)
            ptime = ctime

            # start the tick counter for computing the processing time for each frame
            e1 = cv2.getTickCount()

            # transform the BGR frame in grayscale
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            # apply a bilateral filter to lower noise but keep frame details
            gray = cv2.bilateralFilter(gray, 5, 10, 10)

            # find the faces using the dlib face detector
            faces = Detector(gray)

            if len(faces) <= 0:
                with open('session.txt', 'r') as file:
                    content = file.read()
                    print("File Content:\n", content)
                    
                log_activity(content, "Student is present")
                
                import pyttsx3
                engine = pyttsx3.init()
                engine.say("Student is not Present")
                engine.runAndWait()
                
                

            if len(faces) > 0:  # process the frame only if at least a face is found

                # take only the bounding box of the biggest face
                faces = sorted(faces, key=get_face_area, reverse=True)
                driver_face = faces[0]

                # predict the 68 facial keypoints position
                landmarks = Predictor(gray, driver_face)

                # shows the eye keypoints (can be commented)
                Eye_det.show_eye_keypoints(
                    color_frame=frame, landmarks=landmarks)

                # compute the EAR score of the eyes
                ear = Eye_det.get_EAR(frame=gray, landmarks=landmarks)

                # compute the PERCLOS score and state of tiredness
                tired, perclos_score = Scorer.get_PERCLOS(ear)

                # compute the Gaze Score
                gaze = Eye_det.get_Gaze_Score(
                    frame=gray, landmarks=landmarks)

                # compute the head pose
                frame_det, yaw, pitch, roll = Head_pose.get_pose(
                    frame=frame, landmarks=landmarks, prev_landmarks=prev_landmarks, smoothing_factor=args.smooth_factor)
                # update the previous landmarks
                prev_landmarks = landmarks

                # if the head pose estimation is successful, show the results
                if frame_det is not None:
                    frame = frame_det

                # show the real-time EAR score
                if ear is not None:
                    cv2.putText(frame, "EAR:" + str(round(ear, 3)), (10, 50),
                                cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 1, cv2.LINE_AA)

                # show the real-time Gaze Score
                if gaze is not None:
                    cv2.putText(frame, "Gaze Score:" + str(round(gaze, 3)), (10, 80),
                                cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 1, cv2.LINE_AA)

                # show the real-time PERCLOS score
                cv2.putText(frame, "PERCLOS:" + str(round(perclos_score, 3)), (10, 110),
                            cv2.FONT_HERSHEY_PLAIN, 2, (255, 255, 255), 1, cv2.LINE_AA)

                # if the driver is tired, show and alert on screen
                if tired:
                    cv2.putText(frame, "TIRED!", (10, 280),
                                cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 1, cv2.LINE_AA)

                # evaluate the scores for EAR, GAZE and HEAD POSE
                asleep, looking_away, distracted = Scorer.eval_scores(ear_score=ear,
                                                                      gaze_score=gaze,
                                                                      head_roll=roll,
                                                                      head_pitch=pitch,
                                                                      head_yaw=yaw,
                                                                      )
                print(asleep)
                print(looking_away)
                print(distracted)

                # if the state of attention of the driver is not normal, show an alert on screen
                if asleep :
                    with open('session.txt', 'r') as file:
                        content = file.read()
                        print("File Content:\n", content)
                    if(a==0):
                        log_activity(content, "asleep")
                        a==1
                        b=0
                        c=0
                        d=0
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.say("Please Concentrate on Learning")
                    engine.runAndWait()
                    cv2.putText(frame, "ASLEEP!", (10, 300),
                                cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 1, cv2.LINE_AA)
                if looking_away:
                    with open('session.txt', 'r') as file:
                        content = file.read()
                        print("File Content:\n", content)
                    if(b==0):
                        log_activity(content, "looking_away")
                        b=1
                        a=0
                        c=0
                        d=0
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.say("please Concentrate on Learning")
                    engine.runAndWait()
                    cv2.putText(frame, "LOOKING AWAY!", (10, 320),
                                cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 1, cv2.LINE_AA)
                if distracted:
                    with open('session.txt', 'r') as file:
                        content = file.read()
                        print("File Content:\n", content)
                    if(c==0):
                        b=0
                        a=0
                        c=1
                        d=0
                        log_activity(content, "distracted")
                    import pyttsx3
                    engine = pyttsx3.init()
                    engine.say("Please Concentrate on Learning")
                    engine.runAndWait()
                    cv2.putText(frame, "DISTRACTED!", (10, 340),
                                cv2.FONT_HERSHEY_PLAIN, 1, (0, 0, 255), 1, cv2.LINE_AA)
                if (distracted == False and looking_away == False and asleep == False):
                    print("Normal")
                    if(d==0):
                        with open('session.txt', 'r') as file:
                            content = file.read()
                        print("File Content:\n", content)
                        b=0
                        a=0
                        c=0
                        d=1
                        log_activity(content, "Active")
                    

            # stop the tick counter for computing the processing time for each frame
            e2 = cv2.getTickCount()
            # processign time in milliseconds
            proc_time_frame_ms = ((e2 - e1) / cv2.getTickFrequency()) * 1000
            # print fps and processing time per frame on screen
            if args.show_fps:
                cv2.putText(frame, "FPS:" + str(round(fps, 0)), (10, 400), cv2.FONT_HERSHEY_PLAIN, 2,
                            (255, 0, 255), 1)
            if args.show_proc_time:
                cv2.putText(frame, "PROC. TIME FRAME:" + str(round(proc_time_frame_ms, 0)) + 'ms', (10, 430), cv2.FONT_HERSHEY_PLAIN, 2,
                            (255, 0, 255), 1)

            # show the frame on screen
            cv2.imshow("Press 'q' to terminate", frame)
            current_url = driver.current_url
            if 'https://workspace.google.com/products/meet/' in current_url:
                print("This is a Google Meet URL.")
                f=0
            else:
                print("This is not a Google Meet URL.")
                with open('session.txt', 'r') as file:
                        content = file.read()
                        print("File Content:\n", content)
                
                if(f==0):
                    b=1
                    a=0
                    c=0
                    d=0
                    f=1
                    log_activity(content, "Some other url is openend")
            #time.sleep(5)

        # if the key "q" is pressed on the keyboard, the program is terminated
        if cv2.waitKey(20) & 0xFF == ord('q'):
            driver.quit()
            break

    cap.release()
    cv2.destroyAllWindows()

    return


if __name__ == "__main__":
    main()

from __future__ import division
import global_settings as gs
from datetime import datetime
from twisted.python import log
try:
    import subprocess32 as sbp
except ImportError:
    import subprocess as sbp
import multiprocessing as mp
import AUVSIcv
import signal
import shutil
import shlex
import json
import time
import glob
import cv2
import os


class BaseCamera(object):
    """Abstract class for a camera, not to be used directly."""

    def __init__(self, zoom=45, shutter=50, ISO=100, aperture=4):

        self.base_path = gs.IMAGES_FOLDER
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)

        self.setParams(zoom=zoom, shutter=shutter, ISO=ISO, aperture=aperture)

    def _getName(self):
        filename = '{formated_time}.jpg'.format(
            formated_time=datetime.now().strftime(gs.BASE_TIMESTAMP)
        )
        return os.path.join(self.base_path, filename)

    def calibrate(self):
        pass

    def isShooting(self):
        return False

    def startShooting(self):
        pass

    def stopShooting(self):
        pass

    def setParams(self, zoom, shutter, ISO, aperture, **kwds):
        log.msg('Setting camera params to zoom:{zoom}, shutter:{shutter}, ISO:{ISO}, aperture:{aperture}'.format(zoom=zoom, shutter=shutter, ISO=ISO, aperture=aperture))
        self.zoom = zoom
        self.shutter = shutter
        self.ISO = ISO
        self.aperture = aperture


class SimulationCamera(BaseCamera):
    def __init__(self, simulate_targets, target_queue=None, *params, **kwds):
        super(SimulationCamera, self).__init__(*params, **kwds)

        self._shooting_proc = None
        self._simulate_targets = simulate_targets
        self.target_queue = target_queue

    def _shootingLoop(self, run):
        """Inifinite shooting loop. To run on separate process."""

        import PixHawk as PH
        import tempfile
        
        base_temp_path = tempfile.mkdtemp()
        temp_data_path = os.path.join(base_temp_path, 'temp.json')
        
        #
        # There is a need to init the pixhawk module
        # because the camera is running on a separate
        # process.
        #
        PH.initPixHawkSimulation()

        base_path = os.environ['AUVSI_CV_DATA']
        log.msg('base_path=' + base_path)
        imgs_paths = sorted(glob.glob(os.path.join(base_path, 'renamed_images', '*.jpg')))
        img_index = 0
        target_set = []
        while run.value == 1:
            #
            # Pick up an image from disk
            #
            img_path = imgs_paths[img_index]
            time_stamp = os.path.split(img_path)[-1][:-4]
            new_name = os.path.join(self.base_path, os.path.split(img_path)[-1])

            img_index = (img_index+1) % len(imgs_paths)

            if self._simulate_targets:
                #
                # When simulating targets, there is a need to
                # load the image from disk, paste a target on
                # it and resave on disk. In the process the
                # exif thumbnail is not updated and therefor
                # the resized image will need to be done using
                # opencv. This process is slower than just copying
                # the image and therefore it is not a good idea
                # to do this on the odroid.
                #
                # Get the corresponding data
                #
                with open(temp_data_path, 'wb') as f:
                    json.dump(PH.queryPHdata(time_stamp), f)
                    
                #
                # Load the image
                #
                try:
                    img = AUVSIcv.Image(img_path, data_path=temp_data_path, K=AUVSIcv.global_settings.K)
                except:
                    continue
                
                #
                # Add a target.
                #
                try:
                    if not target_set:
                        print 'creating targets'
                        for i in range(300):
                            #
                            # Create a target.
                            #
                            target, _, _ = AUVSIcv.randomTarget(
                                altitude=0,
                                longitude=-76.6993009944,
                                latitude=38.8515321606,
                                coords_offset=0.005
                            )
                            print 'Created target:', type(target)
                            target_set.append(target)
                    
                    #
                    # Paste it on the image.
                    #
                    for target in target_set:
                        print 'Pasting target'
                        img.paste(target)

                    #
                    # Save the image to disk (should trigger the image processing code).
                    #
                    cv2.imwrite(new_name, img.img)

                except:
                    raise
            else:
                #
                # Save the image to disk (should trigger the image processing code).
                #
                shutil.copyfile(img_path, new_name)

            if self.target_queue:
                img_time = datetime.strptime(time_stamp, gs.BASE_TIMESTAMP)
                self.target_queue.put((new_name, img_time), False)

            #
            # fps = 2
            #
            time.sleep(0.5)

    def calibrate(self):
        pass

    def isShooting(self):
        return self._shooting_proc is not None

    def startShooting(self):
        log.msg('Simulation camera is starting to shoot.')

        self._run_flag = mp.Value('i', 1)
        self._shooting_proc = mp.Process(target=self._shootingLoop, args=(self._run_flag, ))
        self._shooting_proc.start()

    def stopShooting(self):
        if self._shooting_proc is None:
            return

        #
        # Stop the loop
        #
        self._run_flag.value = 0
        self._shooting_proc.join()
        self._shooting_proc = None
        log.msg('Simulation camera stopped shooting.')



def kill(proc_pid):
    """
    Recursively kill a processes and all its children.
    Taken from: http://stackoverflow.com/questions/4789837/how-to-terminate-a-python-subprocess-launched-with-shell-true/4791612#4791612
    """

    import psutil

    process = psutil.Process(proc_pid)

    for proc in process.get_children(recursive=True):
        proc.kill()

    process.kill()


class CanonCamera(BaseCamera):
    def __init__(self, *params, **kwds):

        rec_cmd = 'rec'
        init_cmd = """\"luar enter_alt();
            call_event_proc('SS.Create');
            call_event_proc('SS.MFOn');
            set_prop(222,0);
            set_focus(65000);
            set_prop(272,0);
            set_prop(105,3);
            set_zoom_speed(1);
            set_lcd_display(0);\""""

        self._blocking_cmds(rec_cmd, init_cmd)
        self._shooting_proc = None
        self._set_zoom = True

        super(CanonCamera, self).__init__(*params, **kwds)

    def _nonblocking_cmds(self, *cmds):

        full_cmd = " ".join([gs.CHDKPTP_PATH, '-c'] + ['-e'+cmd for cmd in cmds] + ['-e"q"'])
        log.msg('Executing cmd: {cmd}'.format(cmd=full_cmd))

        p = sbp.Popen(
            shlex.split(full_cmd)
        )
        return p

    def _blocking_cmds(self, *cmds):

        full_cmd = " ".join([gs.CHDKPTP_PATH, '-c'] + ['-e'+cmd for cmd in cmds] + ['-e"q"'])
        log.msg('Executing cmd: {cmd}'.format(cmd=full_cmd))

        result = sbp.call(
            full_cmd,
            shell=True
        )
        return result

    def setParams(self, **kwds):

        super(CanonCamera, self).setParams(**kwds)

        if 'zoom' in kwds and self._set_zoom:
            zoom_cmd = """\"luar set_zoom({zoom})\"""".format(zoom=self.zoom)
            self._blocking_cmds(zoom_cmd)
            self._set_zoom = False

    def isShooting(self):
        return self._shooting_proc is not None

    def startShooting(self):
        """Start the processing of shooting"""

        log.msg('Canon camera is starting to shoot.')

        if self._shooting_proc is not None:
            #
            # The camera is already shooting
            #
            return

        shoot_cmd = """\"remoteshoot {local_folder} -tv=1/{shutter} -sv={ISO} -av={aperture} -cont=9000\"""".format(
            local_folder=gs.IMAGES_FOLDER,
            shutter=self.shutter,
            ISO=self.ISO,
            aperture=self.aperture
        )

        self._shooting_proc = self._nonblocking_cmds(shoot_cmd)

    def stopShooting(self):
        """Stop the processing of shooting"""

        if self._shooting_proc is None:
            #
            # The camera is currently not shooting
            #
            return

        kill(self._shooting_proc.pid)
        self._shooting_proc = None

        self._blocking_cmds('killscript')

        log.msg('Canon camera stopped shooting.')

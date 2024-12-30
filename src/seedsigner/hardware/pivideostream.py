# import the necessary packages
import logging
import subprocess
import threading
import time
import os
from PIL import Image


logger = logging.getLogger(__name__)

class PiVideoStream:
    def __init__(self, device='/dev/video12', resolution=(2304,1296), pixelformat='NV12', framerate=10):
        self.device = device
        self.width, self.height = resolution
        self.pixelformat = pixelformat
        self.framerate = framerate
        if pixelformat == "NV12":
            self.frame_size = self.width * self.height * 3 // 2  # NV12 format size calculation
        else:
            self.frame_size = self.width * self.height # GreyScale format size calculation
        self.frame = None
        self.should_stop = False
        self.is_stopped = True
        self.lock = threading.Lock()  # Thread-safe frame handling
        self.save_path = './saved_frames'  # Directory to save images (both pre and post conversion)
        if not os.path.exists(self.save_path):
            os.makedirs(self.save_path)  # Ensure the save directory exists
        print(f"Initialized PiVideoStream with device={device}, resolution={resolution}, "
              f"pixelformat={pixelformat}, framerate={framerate}")

    def start(self):
        print("Starting video stream...")
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()
        self.is_stopped = False
        return self

    def update(self):
        cmd = [
            'v4l2-ctl',
            f'--device={self.device}',
            f'--set-fmt-video=width={self.width},height={self.height},pixelformat={self.pixelformat}',
            '--stream-mmap',
            '--stream-to=-',
            '--stream-count=0'  # Infinite stream
        ]
        
        print(f"Running command: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=10 * self.frame_size
        )



        while not self.should_stop:
            try:
                start_time = time.time()

                # Read frame data
                frame_data = process.stdout.read(self.frame_size)
                read_time = time.time() - start_time

                if len(frame_data) < self.frame_size:
                    print(f"Incomplete frame data received: {len(frame_data)} bytes")
                    break

                print(f"Frame read time: {read_time:.6f} seconds")
                start_processing = time.time()

                with self.lock:
                    # DEBUG: Save NV12 frame TO DISK (Optional)
                    # WILL QUICKLY FILL UP SPACE
                    # self.save_pre_rgb(frame_data)

                    # Record time for conversion
                    start_conversion = time.time()
                    if self.pixelformat == "NV12":
                        # Python Implementation
                        # self.frame = self.nv12_to_rgb(frame_data)
                        # C Implementation
                        self.frame = self.nv12_to_rgb_subprocess(frame_data, self.width, self.height)
                    elif self.pixelformat == "GREY":
                        self.frame = self.grey_to_pil(frame_data, self.width, self.height)
                    else:
                        self.frame = None
                        raise Exception("Unable to read from camera")

                    conversion_time = time.time() - start_conversion
                    print(f"{self.pixelformat} to PIL Image conversion time: {conversion_time:.6f} seconds")

                    # Save RGB image (optional, for debugging)
                   # self.save_post_rgb(self.frame)

                processing_time = time.time() - start_processing
                print(f"Frame processing time (read+conversion): {processing_time:.6f} seconds")

            except Exception as e:
                print(f"Error while reading frame: {e}")
                break

        process.terminate()
        process.wait()
        self.is_stopped = True
        print("Video stream stopped.")

    def read(self):
        with self.lock:
            if self.frame is not None:
                pass
                # print(f"Reading frame: {self.frame.size}")
            else:
                #print("No frame available to read.")
                iii =0 
            return self.frame

    def stop(self):
        print("Stopping video stream...")
        self.should_stop = True
        while not self.is_stopped:
            time.sleep(0.01)
        print("Video stream stopped successfully.")

    def nv12_to_rgb(self, frame_data):
        """
        Converts NV12 format to a PIL RGB Image with optimized computation.
        
        Args:
            frame_data (bytes): NV12 frame data.
            
        Returns:
            Image: PIL Image in RGB format.
        """
        WIDTH = 240
        HEIGHT = 135

        # Precise frame size calculations
        y_size = WIDTH * HEIGHT  # Luma (Y) plane size
        uv_width = (WIDTH + 1) // 2  # Chroma plane width
        uv_height = (HEIGHT + 1) // 2  # Chroma plane height
        uv_size = uv_width * uv_height * 2  # UV plane size (interleaved U and V)

        # Slice the planes
        y_plane = frame_data[:y_size]
        uv_plane = frame_data[y_size:y_size + uv_size]

        # Constants for YUV to RGB conversion
        YUV_TO_RGB = [
            (1.402, 0),     # YUV -> RGB Conversion constants for R
            (-0.344136, -0.714136),  # YUV -> RGB Conversion constants for G
            (1.772, 0)      # YUV -> RGB Conversion constants for B
        ]

        # Initialize bytearray for RGB data
        rgb_data = bytearray(WIDTH * HEIGHT * 3)

        # Convert NV12 (YUV) to RGB (PIL-compatible)
        idx = 0
        for i in range(HEIGHT):
            for j in range(WIDTH):
                y_index = i * WIDTH + j
                uv_index = (i // 2) * uv_width + (j // 2)

                # Get Y value (luma component)
                y = y_plane[y_index] if y_index < y_size else 0

                # Handle UV values (chroma components)
                u = uv_plane[2 * uv_index] - 128 if 2 * uv_index < len(uv_plane) else 0
                v = uv_plane[2 * uv_index + 1] - 128 if 2 * uv_index + 1 < len(uv_plane) else 0

                # Apply YUV to RGB conversion (with clamping)
                r = y + YUV_TO_RGB[0][0] * v
                g = y + YUV_TO_RGB[1][0] * u + YUV_TO_RGB[1][1] * v
                b = y + YUV_TO_RGB[2][0] * u

                # Clamp RGB values
                rgb_data[idx] = min(max(int(r), 0), 255)
                rgb_data[idx + 1] = min(max(int(g), 0), 255)
                rgb_data[idx + 2] = min(max(int(b), 0), 255)

                # Move to the next RGB pixel
                idx += 3

        # Create a PIL image from the RGB data
        img = Image.frombytes('RGB', (WIDTH, HEIGHT), bytes(rgb_data))

        # Resize if necessary (e.g., for a display resolution of 240x240)
        if WIDTH != 240 or HEIGHT != 240:
            img = img.resize((240, 240))

        return img



    def nv12_to_rgb_subprocess(self, frame_data, width, height):
        """
        Converts NV12 format to a PIL RGB Image using a C subprocess.

        Args:
            frame_data (bytes): NV12 frame data.

        Returns:
            Image: PIL Image in RGB format.
        """
        # WIDTH = 240
        # HEIGHT = 135
        WIDTH = width
        HEIGHT = height

        # Declare Temporary Files
        rgb_file = "/tmp/rgb_frame.bin"
        nv12_file = "/tmp/nv12_frame.bin"

        # Save NV12 frame data to a temporary file
        with open(nv12_file, "wb") as f:
            f.write(frame_data)

        # Run the C converter subprocess
        cmd = [
            "/nv12_converter",
            nv12_file,
            rgb_file,
            str(WIDTH),
            str(HEIGHT),
        ]
        subprocess.run(cmd, check=True)

        # Load the RGB data from the output file
        with open(rgb_file, "rb") as f:
            rgb_data = f.read()

        # Create a PIL image from the RGB data
        img = Image.frombytes("RGB", (WIDTH, HEIGHT), rgb_data)

        # Resize if necessary (e.g., for a display resolution of 240x240)
        # Should I instead crop, then resize to minimize the distortion?
        if WIDTH != 240 or HEIGHT != 240:
            # img = self.crop_to_square(img)
            img = img.resize((240, 240))

        # Clean up temporary files
        os.remove(nv12_file)
        os.remove(rgb_file)

        return img
        # return img.tobytes()

    # def grayscale_to_img(

    def grey_to_pil(self, frame_data, width, height):
        """
        Converts grayscale bytes to a PIL Image.

        Args:
            frame_data (bytes): Grayscale frame data.
            width (int): Width of the frame.
            height (int): Height of the frame.

        Returns:
            Image: PIL Image in Grayscale format.
        """
        # Create a PIL image from the grayscale data
        img = Image.frombytes("L", (width, height), frame_data)

        # Resize if necessary (e.g., for a display resolution of 240x240)
        if width != 240 or height != 240:
            # img = self.crop_to_square(img)
            img = img.resize((240, 240))

        return img    



    def save_pre_rgb(self, frame_data):
        """
        Save the NV12 frame data as an image file before RGB conversion.

        Args:
            frame_data (bytes): NV12 frame data.
        """
        nv12_image_path = os.path.join(self.save_path, f"frame_{time.time()}.nv12")
        with open(nv12_image_path, 'wb') as f:
            f.write(frame_data)
        print(f"Saved pre-RGB frame to {nv12_image_path}")

    def save_post_rgb(self, rgb_image):
        """
        Save the RGB image after conversion.

        Args:
            rgb_image (Image): PIL Image in RGB format.
        """
        rgb_image_path = os.path.join(self.save_path, f"frame_{time.time()}.png")
        rgb_image.save(rgb_image_path)
        print(f"Saved post-RGB frame to {rgb_image_path}")



    def crop_to_square(self, image):
        width, height = image.size
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size
        return image.crop((left, top, right, bottom))
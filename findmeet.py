import cv2
from skimage import data, img_as_float
from skimage.metrics import structural_similarity as ssim

def ssim_compare(img1_path, img2_path) :
    img1 = cv2.imread(img1_path, 0)
    img2 = cv2.imread(img2_path, 0)
    dim = (6022,5513)
    img1 = cv2.resize(img1, dim)
    img2 = cv2.resize(img2, dim)
    ssim_score, dif = ssim(img1, img2, full=True)
    return ssim_score


ssim_val = ssim_compare('1.png', '1.png')
print(ssim_val)


#!/usr/bin/env python3
import argparse
import sys,os
from PIL import Image, ImageDraw
import cv2
from matplotlib import pyplot as plt
import numpy as np
from sklearn.cluster import KMeans
from tqdm import tqdm
import warnings
import multiprocessing as mp
import matplotlib


def centroid_histogram(clt):
	# grab the number of different clusters and create a histogram
	# based on the number of pixels assigned to each cluster
	numLabels = np.arange(0, len(np.unique(clt.labels_)) + 1)
	(hist, _) = np.histogram(clt.labels_, bins = numLabels)
	# normalize the histogram, such that it sums to one
	hist = hist.astype("float")
	hist /= hist.sum()
	# return the histogram
	return hist

def plot_colors(hist, centroids,size=None):
	# initialize the bar chart representing the relative frequency
	# of each of the colors
	if size==None:
		length = 300
	else:
		length = size[0]
	bar = np.zeros((500, length, 3), dtype = "uint8")
	startX = 0
	# loop over the percentage of each cluster and the color of
	# each cluster
	for (percent, color) in zip(hist, centroids):
		# plot the relative percentage of each cluster
		endX = startX + (percent * length)
		cv2.rectangle(bar, (int(startX), 0), (int(endX), 500),
			color.astype("uint8").tolist(), -1)
		startX = endX
	
	# return the bar chart
	return bar

def get_colors_quick(frame, resize=150):
    # Resize image to speed up processing
    img = Image.fromarray(np.uint8(frame))
    #img = img.copy()
    img.thumbnail((resize, resize))

    # Reduce to palette
    paletted = img.convert('P', palette=Image.ADAPTIVE, colors=10)

    # Find dominant colors
    palette = paletted.getpalette()
    color_counts = sorted(paletted.getcolors(), reverse=True)
    palette_index = color_counts[0][1]
    dominant_color = palette[palette_index*3:palette_index*3+3]
    return tuple(dominant_color)

def countframes(path):
	video = cv2.VideoCapture(path)
	total = 0
	# if the override flag is passed in, revert to the manual
	# method of counting frames
	try:
		if is_cv3(or_better=True):
			total = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
		else:
			total = int(video.get(cv2.cv.CV_CAP_PROP_FRAME_COUNT))
	except Exception as e:
		video.release()
		print("Error in getting total frames",e)
		return -1
	video.release()
	return total

def get_opencv_major_version(lib=None):
    # if the supplied library is None, import OpenCV
    if lib is None:
        import cv2 as lib

    # return the major version number
    return int(lib.__version__.split(".")[0])


def is_cv3(or_better=False):
    # grab the OpenCV major version number
    major = get_opencv_major_version()

    # check to see if we are using *at least* OpenCV 3
    if or_better:
        return major >= 3

    # otherwise we want to check for *strictly* OpenCV 3
    return major == 3

def read_movie(path):
	vidcap = cv2.VideoCapture(path)
	movie = []

	success,imageshow = vidcap.read()
	if success==False:
		print("Could not open movie")
		return
	else:
		head,tail = os.path.split(path)
		filename = tail.rsplit(".")[0]
		print("Reading movie: %s\n"%filename)
	totalframes = countframes(path)
	if totalframes != -1:
		pbar = tqdm(total=totalframes)

	count = 0
	while True:
	    ret, frame = vidcap.read()
	    if ret == True:
	        b = cv2.resize(frame,(256,144),fx=0,fy=0, interpolation = cv2.INTER_CUBIC)
	        movie.append(b)
	        if totalframes!=-1:
	        	pbar.update(1)
	    else:
	        break
	vidcap.release()
	pbar.close()
	return movie

def resample(movie,samplingrate):

	moviedownsampled = []
	idx=0
	count=0
	average = []

	#use tqdm for nice progress bar
	print("Resampling movie\n")
	pbar = tqdm(total=len(movie))
	
	while idx<len(movie):
	    average.append(movie[idx])
	    idx = idx+1
	    count = count+1
	    if count==samplingrate:
	        moviedownsampled.append(np.mean(average,axis=0))
	        count=0      
	        average = []
	        pbar.update(samplingrate)

	pbar.close()
	return moviedownsampled

def moviebarcode(colors):
	bar = np.zeros((500, len(colors), 3), dtype = "uint8")
	startX = 0
	# loop over the percentage of each cluster and the color of
	# each cluster
	for color in colors:
	    # plot the relative percentage of each cluster
	    endX = startX + 1
	    cv2.rectangle(bar, (int(startX), 0), (int(endX), 500),
	        color, -1)
	    startX = endX
	return bar

def main():
	parser = argparse.ArgumentParser(prog="generator",description="Generate a color profile of an entire movie or a particular scene")

	parser.add_argument('mode',action="store",help='use m to run the program to generate a barcode for movie, s to generate color-profile for a scene')
	parser.add_argument('path',action="store",help="specify the path of the movie/scene")
	parser.add_argument('-length',action="store",type=int,help="optional argument, the length of the barcode",required=False)
	parser.add_argument('-colors',action="store",type=int,help="optional argument, the number of primary colors to be found in the scene",required=False)

	args = parser.parse_args()
	#print(args.mode,args.length,args.colors,args.path)

	#set some default values for the plots
	plt.rcParams['savefig.facecolor']='#252525'
	if args.mode=='m':
		movie = read_movie(args.path)
		if args.length == None:
			samplingrate = np.floor(len(movie)/1440)
		else:
			samplingrate = np.floor(len(movie)/args.length)
		downsampled = resample(movie,samplingrate)
	
		colorarray = []
		print("Generating bar code\n")
		for idx in tqdm(range(0,len(downsampled))):
			colorarray.append(get_colors_quick(downsampled[idx]))

		bar = moviebarcode(colorarray)
		plt.figure(figsize=(6,8))
		#plt.title('',fontdict={'fontfamily':'fantasy'})
		plt.axis("off")
		plt.imshow(bar)
		# plt.rcParams['axes.facecolor']='r'
		# plt.rcParams['axes.linewidth'] = 5
		#get file name
		head,tail = os.path.split(args.path)
		filename = tail.rsplit(".")[0]
		plt.savefig(filename+"_barcode.png",bbox_inches="tight")

	elif args.mode=='s':

		scene = Image.open(args.path)
		if args.colors == None:
			numberofcolors = 10
		else:
			numberofcolors = args.colors
		
		image = np.asarray(scene)
		image = image.reshape((image.shape[0] * image.shape[1], 3))
		clt = KMeans(n_clusters = numberofcolors)
		clt.fit(image)

		hist = centroid_histogram(clt)
		bar = plot_colors(hist, clt.cluster_centers_,scene.size)

		fig,ax = plt.subplots(nrows=2,ncols=1,figsize=(6,8))

		ax[0].imshow(scene,aspect="equal")
		ax[1].imshow(bar,aspect="equal")
		ax[0].set_xticks([])
		ax[1].set_xticks([])
		ax[0].set_yticks([])
		ax[1].set_yticks([])
		fig.subplots_adjust(hspace=0)
		head,tail = os.path.split(args.path)
		filename = tail.rsplit(".")[0]
		#fig=figure(facecolor='black')
		plt.savefig(filename+'_primarycolors.png',bbox_inches="tight")
	else:
		print("Improper usage, use  main -h to see the proper usage. Exiting...")
		return 


if __name__ == "__main__":
	main()

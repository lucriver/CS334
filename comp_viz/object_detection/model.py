# Author(s): Lucas Hirt
# Date Modified: 11/27/2022

import mxnet
import gluoncv
import numpy
import time

from .. import utils

try:
    a = mxnet.nd.zeros((1,), ctx=mxnet.gpu())
    ctx = [mxnet.gpu()]
except:
    ctx = [mxnet.cpu()]

class Model:
  """Computer vision object detection model.

  :param network_name: A string representing the computer vision network that will be used
                       for detection.
  :type network_name: string
  :ivar net_name: Holds the string literal for the chosen computer vision network.
  :ivar net: Holds the crucial mxnet-gluoncv instantiated computer vision model for which
             our package aims to provides a layer of abstraction over.
  :ivar inference_resolution: Stores the resolution of images we are to perform inference on.
  :ivar _default_object_classes: Stores the default object classes that come with chosen network:
  """

  def __init__(self,network_name):
    """Constructor method
    """
    print(ctx)
    if network_name not in utils.ObjectDetection.get_networks():
      raise ValueError(f"{network_name} is an invalid network.")
    self.net_name = network_name
    self.net = gluoncv.model_zoo.get_model(network_name, pretrained=True, ctx=ctx)
    self.inference_resolution = utils.ObjectDetection.get_network_resolution(network_name)
    self._default_object_classes = gluoncv.model_zoo.get_model(network_name, pretrained=True).classes
    print("Model successfully initialized.")

  def list_classes(self):
    """Print the object classes that the computer vision model is detecting for in images.
    
    :rtype: void
    """
    print(self._get_classes())

  def get_classes(self):
    """Get list of the object classes that the computer vision model is detecting for in images.
    
    :rtype: List
    """
    return (self._get_classes())

  def get_prediction(self,fname,nms=0.) -> dict:
    """Get prediction made for an image by computer vision model.
    
    :param fname: Path to an image file.
    :type fname: string
    :param nms: Stands for non-maximal suppresion. If computer vision model detects and an 
                object in the image with a confidence value less than the nms value, it 
                will not include it in the returned results. 
    :type nms: float
    :rtype: dict            
    """
    utils.Tools.verify_exists(fname)
    start = time.time()
    cids, scores, bboxes = self._predict(fname,nms)
    end = time.time()
    prediction = {}
    prediction["image"] = str(fname)
    prediction['class_ids'] = cids
    prediction['confidence_scores'] = scores
    prediction['bounding_boxes'] = bboxes
    prediction['nms_thresh'] = nms
    prediction['class_map'] = {cid: self.get_classes()[cid] for cid in set(cids)}
    prediction['time'] = round(float(end - start),4)
    prediction['network'] = self.net_name
    prediction['resolution'] = self.inference_resolution
    return prediction

  def get_image_prediction(self,fname,nms=0.):
    """Get image with the bounding box detections and the prediction made by the computer vision model.
    
    :param fname: Path to an image file.
    :type fname: string
    :param nms: Stands for non-maximal suppresion. If computer vision model detects and an 
                object in the image with a confidence value less than the nms value, it 
                will not include it in the returned results.
    :type nms: float
    :return: A pair of values, an image in the form of a numpy array, and the prediction dict.
    :rtype: (numpy.array, dict)
    """
    pred = self.get_prediction(fname,nms)
    pred_img = utils.ObjectDetection.get_pred_bboxes_image(fname,
                                                           pred["bounding_boxes"],
                                                           pred["class_ids"],
                                                           [val for val in pred["class_map"].values()],
                                                           pred["confidence_scores"])
    return pred_img, pred

  def show_image_prediction(self,fname,nms=0.):
    """Print image with the bounding box detections and the prediction made by the computer vision model.
    
    :param fname: Path to an image file.
    :type fname: string
    :param nms: Stands for non-maximal suppresion. If computer vision model detects and an 
                object in the image with a confidence value less than the nms value, it 
                will not include it in the returned results.
    :type nms: float
    :rtype: void
    """
    image, prediction = self.get_image_prediction(fname)
    utils.Tools.show_image(image)
    print(prediction)

  def set_classes(self,object_classes: list):
    """Change the object classes that the computer vision model is detecting for in images. Ensures validity by referencing the original list of available object classes when model was first instantiatied.
    
    :param object_classes: List of new object classes to detect for. Ex. "person", "bicycle", "banana".
    :type object_classes: List
    :rtype: void
    """
    unsupported = []
    for obj_class in object_classes:
      if obj_class not in self._default_object_classes:
        unsupported.append(obj_class)
    if unsupported:    
      raise ValueError(f"Object class(es) \"{unsupported}\" are not supported for object detection.")
    self.net.reset_class(object_classes, reuse_weights=object_classes)
    print(f"Complete. Model set to detect for object classes: {self.get_classes()}.")

  def reset_classes(self):
    """Change the object classes that the computer vision model is detecting for in images back to defaults.

    :rtype: void
    """
    self.net.reset_class(self._default_object_classes,reuse_weights=self._default_object_classes)
    print("Object classes for detection restored to defaults.")

  def set_inference_resolution(self,res):
    """Alter the resolution of the image that is input to the model to get prediction for. Can effect speed and precision of model.

    :param res: Desired resolution of image.
    :type res: int
    :rtype: void
    """
    if res < 1 or res > 1024:
      raise ValueError(f"{res} is too small or too large of value.")
    self._set_inference_resolution(res)

  # Change actual object attribute's inference_resolution value.
  def _set_inference_resolution(self,res):
    self.inference_resolution = res

  # Get tuple containing class ids, confidence scores and bounding boxes for an image prediction,
  # apply NMS if specified and return the tuple.
  def _predict(self,fname,nms) -> tuple:
    base_img = mxnet.image.imread(fname)
    x, img = self.__prepare_image(base_img)
    pred = self.net(x.as_in_context(ctx[0]))
    cids, scores, bboxes = self._extract_cids_scores_bboxes(pred)
    # resize bounding box from network inference resolution to original image resolution
    bboxes = [utils.ObjectDetection.resize_bbox(bbox,img.shape,base_img.shape) for bbox in bboxes]
    if nms == 0:
      return (cids,scores,bboxes)
    nms_cids, nms_scores, nms_bboxes = self._apply_nms(cids, scores, bboxes, nms)
    return (nms_cids,nms_scores,nms_bboxes)

  # Get the CURRENT object classes for the model.
  def _get_classes(self):
    return self.net.classes
    
  # Return tuple containing only the class ids, confidence scores, and bounding boxes of an MXNet
  # inference result.
  def _extract_cids_scores_bboxes(self,pred):
    cids = self._get_class_ids(pred[0])
    scores = self._get_scores(pred[1])
    bboxes = self._get_bboxes(pred[2])
    return (cids, scores, bboxes)

  # Given an tuple containing class ids, confidence scoers and bounding boxes for an MXNet prediction
  # filter the results and return them based off the confidence scores of the predictions and the
  # specified nms value. (If confidence score < NMS, prune that prediction from results to be returned.)
  def _apply_nms(self,cids: list, scores: list, bboxes: list, nms: float):
    prune_indexes = []
    for i, score in enumerate(scores):
      if score < nms:
        prune_indexes.append(i)
    for index in prune_indexes[::-1]:
      cids.pop(index)
      scores.pop(index)
      bboxes.pop(index)
    return (cids, scores, bboxes)

  # Extract the class ids from an MXNet prediction ndarray to a list.
  def _get_class_ids(self,cids: numpy.ndarray) -> list:
    class_ids = []
    for ndarray in cids[0]:
      nparray = ndarray.asnumpy()
      if nparray[0] != -1:
        class_ids.append(int(nparray[0]))
    return class_ids

  # Extract the confidence score float values from an MXNet prediction ndarray to a list
  def _get_scores(self,scores: list):
    confidence_scores = []
    for ndarray in scores[0]:
      nparray = ndarray.asnumpy()
      if nparray[0] != -1:
        confidence_scores.append(round(float(nparray[0]),3))
    return confidence_scores

  # Extract the bounding boxes from an MXNet prediction ndarray to a nested list 
  def _get_bboxes(self,bboxes):
    bounding_boxes = []
    for ndarray in bboxes[0]:
      nparray = ndarray.asnumpy()
      if nparray[0] != -1:
        bb = [float(corner) for corner in nparray.tolist()]
        bounding_boxes.append(bb)
    return bounding_boxes

  # Process image such that inference can be performed by the mxnet network.
  def __prepare_image(self,image):
    if "yolo" in self.net_name:
      return gluoncv.data.transforms.presets.yolo.transform_test(image,short=self.inference_resolution)
    elif "rcnn" in self.net_name:
      return gluoncv.data.transforms.presets.rcnn.transform_test(image,short=self.inference_resolution)
    elif "ssd" in self.net_name:
      return gluoncv.data.transforms.presets.ssd.transform_test(image,short=self.inference_resolution)
    elif "center_net" in self.net_name:
      return gluoncv.data.transforms.presets.center_net.transform_test(image,short=self.inference_resolution)
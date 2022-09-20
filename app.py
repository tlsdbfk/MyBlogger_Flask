import torchvision.transforms as transforms
import torch
import numpy as np
from PIL import Image
from flask import Flask, jsonify, request
from torchvision import transforms
from torchvision import models
from fairseq import utils,tasks
from fairseq import checkpoint_utils
from utils.eval_utils import eval_step
from tasks.mm_tasks.caption import CaptionTask

from MyBlogger import metadata_extract, translate, subject_extract

app = Flask(__name__)

app.config['JSON_AS_ASCII'] = False

# Register caption task
tasks.register_task('caption',CaptionTask)

# turn on cuda if GPU is available
use_cuda = torch.cuda.is_available()
# use fp16 only when GPU is available
use_fp16 = False

# Load pretrained ckpt & config
overrides={"bpe_dir":"utils/BPE", "eval_cider":False, "beam":5, "max_len_b":16, "no_repeat_ngram_size":3, "seed":7}
models, cfg, task = checkpoint_utils.load_model_ensemble_and_task(
        utils.split_paths('utils/BPE/caption.pt'),
        arg_overrides=overrides
    )

# Move models to GPU
for model in models:
    model.eval()
    if use_fp16:
        model.half()
    if use_cuda and not cfg.distributed_training.pipeline_model_parallel:
        model.cuda()
    model.prepare_for_inference_(cfg)

# Initialize generator
generator = task.build_generator(models, cfg.generation)

# Image transform
mean = [0.5, 0.5, 0.5]
std = [0.5, 0.5, 0.5]

patch_resize_transform = transforms.Compose([
    lambda image: image.convert("RGB"),
    transforms.Resize((cfg.task.patch_image_size, cfg.task.patch_image_size), interpolation=Image.BICUBIC),
    transforms.ToTensor(),
    transforms.Normalize(mean=mean, std=std),
])

# Text preprocess
bos_item = torch.LongTensor([task.src_dict.bos()])
eos_item = torch.LongTensor([task.src_dict.eos()])
pad_idx = task.src_dict.pad()
def encode_text(text, length=None, append_bos=False, append_eos=False):
    s = task.tgt_dict.encode_line(
        line=task.bpe.encode(text),
        add_if_not_exist=False,
        append_eos=False
    ).long()
    if length is not None:
        s = s[:length]
    if append_bos:
        s = torch.cat([bos_item, s])
    if append_eos:
        s = torch.cat([s, eos_item])
    return s

# Construct input for caption task
def construct_sample(image: Image):
    patch_image = patch_resize_transform(image).unsqueeze(0)
    patch_mask = torch.tensor([True])
    src_text = encode_text(" what does the image describe?", append_bos=True, append_eos=True).unsqueeze(0)
    src_length = torch.LongTensor([s.ne(pad_idx).long().sum() for s in src_text])
    sample = {
        "id":np.array(['42']),
        "net_input": {
            "src_tokens": src_text,
            "src_lengths": src_length,
            "patch_images": patch_image,
            "patch_masks": patch_mask
        }
    }
    return sample
  
# Function to turn FP32 to FP16
def apply_half(t):
    if t.dtype is torch.float32:
        return t.to(dtype=torch.half)
    return t

#@app.route('/', methods=['GET', 'POST'])
@app.route('/caption', methods=['GET', 'POST'])
def caption():
    if request.method == 'POST':
        # Download an image from COCO or you can use other images with wget
        #image = Image.open('./20191225.jpg')

        f = request.files['proFile']
        f.save("." + "/" + f.filename)
        return f.filename

    else:
        result_data = {}

        import glob
        import os

        list_of_files = glob.glob('./*') # * means all if need specific format then *.csv
        latest_file = max(list_of_files, key=os.path.getctime)
        print(latest_file)

        image = Image.open('.'+'/' + latest_file) #### 이거 이따 수정해야할지도
        #image = Image.open('./picture1.png')

        # Construct input sample & preprocess for GPU if cuda available
        sample = construct_sample(image)
        sample = utils.move_to_cuda(sample) if use_cuda else sample
        sample = utils.apply_to_sample(apply_half, sample) if use_fp16 else sample

        # Run eval step for caption
        with torch.no_grad():
            result, score = eval_step(task, generator, models, sample)

        caption = result[0]['caption']

        caption_sub, caption_str = subject_extract(caption)

        result_caption_sub = translate(caption_sub)
        result_caption_str = translate(caption_str)

        result_data["result_caption"] = translate(caption)

        result_data["result_caption_sub"] = result_caption_sub
        result_data["result_caption_str"] = result_caption_str

        result_metadata = metadata_extract(image)
            
        for data in result_metadata:
            result_data[data] = result_metadata[data]

        return jsonify(result_data)
    
if __name__ == '__main__':
    #app.run()
    app.run(host="192.168.45.152", port=8080)
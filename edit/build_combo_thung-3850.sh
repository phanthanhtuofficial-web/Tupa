#!/bin/bash
# Ghép nguồn cho video "Vàng thủng 3.850": v1.mov + clip 8s (a8) + video cũ 15s (b15) + video cũ 32s (c32).
# Chạy trong thư mục work/ (cần v1.mov, ins/a8.mov, ins/b15.mov, ins/c32.mov). Mốc phải khớp PIECES trong render script.
set -e
mkdir -p pc
V="scale=1080:1920:flags=lanczos,fps=30,setsar=1,format=yuv420p"
E="-c:v libx264 -crf 16 -preset fast -c:a aac -b:a 256k -ar 48000 -ac 2"
ffmpeg -v error -y -ss 0 -t 27.5 -i v1.mov -vf "$V" $E pc/p0.mp4
ffmpeg -v error -y -i ins/a8.mov -vf "delogo=x=3:y=430:w=126:h=96:enable='lt(t,3.45)',delogo=x=402:y=714:w=135:h=98:enable='gte(t,3.2)',trim=0.95:5.55,setpts=PTS-STARTPTS,$V" -af "atrim=0.95:5.55,asetpts=PTS-STARTPTS" $E pc/p1.mp4
ffmpeg -v error -y -ss 27.5 -t 10.7 -i v1.mov -vf "$V" $E pc/p2.mp4
ffmpeg -v error -y -ss 0 -t 9.05 -i ins/b15.mov -vf "$V" $E pc/p3.mp4
ffmpeg -v error -y -ss 9.1 -t 8.65 -i ins/c32.mov -vf "$V" $E pc/p4.mp4
ffmpeg -v error -y -ss 38.2 -i v1.mov -vf "$V" $E pc/p5.mp4
for i in 0 1 2 3 4 5; do echo "file 'p$i.mp4'"; done > pc/list.txt
ffmpeg -v error -y -f concat -safe 0 -i pc/list.txt -c copy v1_combo.mp4

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
# đoạn giữ hình 16.2s (nền đen, im lặng) cho ảnh nhận định
ffmpeg -v error -y -f lavfi -i color=c=black:s=1080x1920:r=30:d=16.2 -f lavfi -i anullsrc=r=48000:cl=stereo -t 16.2 $E -pix_fmt yuv420p pc/ph.mp4
printf "file '%s'\n" p0.mp4 p1.mp4 p2.mp4 ph.mp4 p3.mp4 p4.mp4 p5.mp4 > pc/list.txt
ffmpeg -v error -y -f concat -safe 0 -i pc/list.txt -c copy v1_combo.mp4

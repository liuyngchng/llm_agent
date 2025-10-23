#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (c) [2025] [liuyngchng@hotmail.com] - All rights reserved.

"""
通过 PPT 模板分析用户 PPT 中的内容是否符合规范，直接对报告进行调整不符合模板规范的直接修改  PPT 格式。
"""
from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
from werkzeug.utils import secure_filename
from apps.pptx.ppt_formatter import PPTFormatter

# 初始化 Flask 应用
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['ALLOWED_EXTENSIONS'] = {'pptx'}

# 确保上传目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 检查文件扩展名是否合法
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# 首页路由
@app.route('/')
def index():
    return render_template('index.html')

# 文件上传路由
@app.route('/upload', methods=['GET', 'POST'])
def upload_files():
    if request.method == 'POST':
        # 检查文件是否上传
        if 'template_file' not in request.files or 'source_file' not in request.files:
            return redirect(request.url)
        
        template_file = request.files['template_file']
        source_file = request.files['source_file']
        
        if template_file.filename == '' or source_file.filename == '':
            return redirect(request.url)
        
        if template_file and allowed_file(template_file.filename) and source_file and allowed_file(source_file.filename):
            # 保存上传的文件
            template_filename = secure_filename(template_file.filename)
            source_filename = secure_filename(source_file.filename)
            
            template_path = os.path.join(app.config['UPLOAD_FOLDER'], template_filename)
            source_path = os.path.join(app.config['UPLOAD_FOLDER'], source_filename)
            
            template_file.save(template_path)
            source_file.save(source_path)
            
            # 调用 PPTFormatter 处理文件
            formatter = PPTFormatter()
            template_styles = formatter.extract_template_styles(template_path)
            formatted_ppt = formatter.auto_format_ppt(source_path, template_styles)
            
            # 保存处理后的文件
            output_filename = 'formatted_' + source_filename
            output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
            formatted_ppt.save(output_path)
            
            return redirect(url_for('download_file', filename=output_filename))
    
    return render_template('index.html')

# 文件下载路由
@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
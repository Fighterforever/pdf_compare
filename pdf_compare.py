import os
import re
from pathlib import Path
import datetime
import PyPDF2
import difflib
from tqdm import tqdm  # 用于显示进度条

def extract_title_from_pdf(pdf_path):
    """从PDF文件中提取可能的标题"""
    try:
        # 打开PDF文件
        with open(pdf_path, 'rb') as file:
            # 创建PDF读取器对象
            pdf_reader = PyPDF2.PdfReader(file)
            
            # 检查PDF是否有页面
            if len(pdf_reader.pages) == 0:
                return None
            
            # 从第一页提取文本
            first_page_text = pdf_reader.pages[0].extract_text()
            
            # 如果第一页没有文本，尝试读取第二页
            if not first_page_text and len(pdf_reader.pages) > 1:
                first_page_text = pdf_reader.pages[1].extract_text()
            
            if not first_page_text:
                return None
            
            # 尝试从文本中识别标题
            # 方法1：查找换行符之前的前几行文本（通常标题在顶部）
            lines = first_page_text.split('\n')
            # 过滤掉空行
            lines = [line.strip() for line in lines if line.strip()]
            
            # 跳过可能的期刊标题、日期等，通常论文标题在前几行
            potential_title_lines = []
            for i, line in enumerate(lines[:10]):  # 只考虑前10行
                # 跳过明显不是标题的行（如日期、页码、"Abstract"等）
                if re.search(r'^\d+$|^Vol\.|^Abstract|^Pages|^\d{4}$|^Journal of', line, re.IGNORECASE):
                    continue
                
                # 如果行太短，可能是作者名或其他信息
                if len(line) < 10:
                    continue
                
                # 如果行以常见非标题开头的词开始，跳过
                if re.match(r'^(Received|Submitted|Accepted|Published|Copyright|DOI)', line, re.IGNORECASE):
                    continue
                
                potential_title_lines.append(line)
                
                # 论文标题通常不会很长，所以如果已经收集了1-3行，可能已经包含完整标题
                if i >= 2 and len(potential_title_lines) > 0:
                    break
            
            # 合并可能的标题行
            potential_title = ' '.join(potential_title_lines[:3])  # 最多使用前3行
            
            # 如果找不到可能的标题，返回前100个字符作为备选
            if not potential_title and len(first_page_text) > 100:
                return first_page_text[:100]
            
            return potential_title
    
    except Exception as e:
        print(f"提取标题出错 {pdf_path}: {e}")
        return None

def normalize_title(title):
    """标准化标题以改善匹配"""
    if not title:
        return ""
    # 转换为小写
    title = title.lower()
    # 移除特殊字符和多余空格
    title = re.sub(r'[^\w\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title)
    return title.strip()

def find_similar_titles(folder_a, folder_b, similarity_threshold=0.8, recursive=True):
    """在两个文件夹中查找标题相似的PDF论文
    
    参数:
        folder_a: 第一个文件夹路径
        folder_b: 第二个文件夹路径
        similarity_threshold: 相似度阈值（0到1之间）
        recursive: 是否递归搜索子文件夹
    
    返回:
        包含相似论文信息的列表
    """
    # 存储文件夹A中文件的标题
    folder_a_titles = {}
    
    # 获取所有PDF文件的函数
    def get_pdf_files(folder):
        if recursive:
            return list(Path(folder).glob('**/*.pdf'))
        else:
            return list(Path(folder).glob('*.pdf'))
    
    # 处理文件夹A中的文件
    print(f"正在从文件夹A中提取论文标题: {folder_a}")
    files_a = get_pdf_files(folder_a)
    
    for file_path in tqdm(files_a, desc="处理文件夹A"):
        if file_path.is_file() and file_path.suffix.lower() == '.pdf':
            try:
                title = extract_title_from_pdf(file_path)
                if title:
                    normalized_title = normalize_title(title)
                    relative_path = file_path.relative_to(folder_a)
                    folder_a_titles[str(relative_path)] = {
                        'original': title,
                        'normalized': normalized_title
                    }
            except Exception as e:
                print(f"处理文件出错 {file_path}: {e}")
    
    # 存储相似文件的列表
    similar_papers = []
    
    # 处理文件夹B中的文件并检查相似性
    print(f"\n正在从文件夹B中提取论文标题并比较: {folder_b}")
    files_b = get_pdf_files(folder_b)
    
    for file_path in tqdm(files_b, desc="处理文件夹B"):
        if file_path.is_file() and file_path.suffix.lower() == '.pdf':
            try:
                title_b = extract_title_from_pdf(file_path)
                if title_b:
                    normalized_title_b = normalize_title(title_b)
                    relative_path_b = str(file_path.relative_to(folder_b))
                    
                    # 比较与文件夹A中所有标题的相似度
                    for path_a, title_info_a in folder_a_titles.items():
                        normalized_title_a = title_info_a['normalized']
                        
                        # 使用序列匹配计算相似度
                        similarity = difflib.SequenceMatcher(None, normalized_title_a, normalized_title_b).ratio()
                        
                        if similarity >= similarity_threshold:
                            similar_papers.append({
                                'path_a': path_a,
                                'path_b': relative_path_b,
                                'title_a': title_info_a['original'],
                                'title_b': title_b,
                                'similarity': similarity
                            })
            except Exception as e:
                print(f"处理文件出错 {file_path}: {e}")
    
    # 按相似度排序结果
    similar_papers.sort(key=lambda x: x['similarity'], reverse=True)
    
    return similar_papers

def save_results_to_file(similar_papers, folder_a, folder_b, output_file):
    """将结果保存到文本文件"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("论文标题相似度查找器 - 结果\n")
        f.write("==========================\n\n")
        f.write(f"日期: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"文件夹A: {folder_a}\n")
        f.write(f"文件夹B: {folder_b}\n\n")
        
        if similar_papers:
            f.write(f"找到{len(similar_papers)}对标题相似的论文:\n\n")
            for i, paper in enumerate(similar_papers, 1):
                f.write(f"相似对 #{i} (相似度: {paper['similarity']:.2f}):\n")
                f.write(f"文件夹A: {paper['path_a']}\n")
                f.write(f"标题A: {paper['title_a']}\n")
                f.write(f"文件夹B: {paper['path_b']}\n")
                f.write(f"标题B: {paper['title_b']}\n")
                f.write("-" * 50 + "\n\n")
        else:
            f.write("未找到标题相似的论文。\n")
    
    print(f"结果已保存到 {output_file}")

def main():
    print("论文标题相似度查找器")
    print("====================")
    print("这个脚本提取PDF论文的标题并识别相似的论文。")
    print("注意: 标题提取是基于启发式方法，可能不会对所有论文都准确。\n")
    
    folder_a = input("输入文件夹A的路径: ")
    folder_b = input("输入文件夹B的路径: ")
    
    if not os.path.isdir(folder_a):
        print(f"错误: {folder_a} 不是有效的目录")
        return
    
    if not os.path.isdir(folder_b):
        print(f"错误: {folder_b} 不是有效的目录")
        return
    
    recursive = input("是否在子文件夹中搜索? (y/n): ").lower().startswith('y')
    
    similarity_threshold_input = input("输入标题相似度阈值 (0.0-1.0，推荐0.8): ")
    try:
        similarity_threshold = float(similarity_threshold_input)
        if similarity_threshold < 0 or similarity_threshold > 1:
            print("错误: 相似度阈值必须在0和1之间，将使用默认值0.8")
            similarity_threshold = 0.8
    except ValueError:
        print("错误: 无效的相似度阈值，将使用默认值0.8")
        similarity_threshold = 0.8
    
    print("\n正在搜索标题相似的论文...")
    similar_papers = find_similar_titles(folder_a, folder_b, similarity_threshold, recursive)
    
    if similar_papers:
        print(f"\n找到{len(similar_papers)}对标题相似的论文:")
        for i, paper in enumerate(similar_papers[:10], 1):  # 只显示前10个结果
            print(f"{i}. 相似度: {paper['similarity']:.2f}")
            print(f"   文件夹A: {paper['path_a']}")
            print(f"   标题A: {paper['title_a'][:80]}...")
            print(f"   文件夹B: {paper['path_b']}")
            print(f"   标题B: {paper['title_b'][:80]}...")
            print("")
        
        if len(similar_papers) > 10:
            print(f"... 还有{len(similar_papers) - 10}对相似论文未显示")
    else:
        print("\n未找到标题相似的论文。")
    
    save_to_file = input("\n是否将完整结果保存到文件? (y/n): ").lower().startswith('y')
    if save_to_file:
        output_file = input("输入输出文件路径: ")
        save_results_to_file(similar_papers, folder_a, folder_b, output_file)

if __name__ == "__main__":
    main()

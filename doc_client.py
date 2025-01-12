from typing import List, Callable, Optional
from openai import AsyncOpenAI
import asyncio
from dataclasses import dataclass
import pandas as pd
import os
from datetime import datetime

@dataclass
class GenerationConfig:
    model: str = "gpt-3.5-turbo"
    temperature: float = 0.8
    max_tokens: int = 8192 # 默认输出长度
    base_url: Optional[str] = None
    max_concurrent: int = 50
    preview_limit: int = 10

class DocGeneratorClient:
    def __init__(
        self,
        api_key: str = None,
        config: GenerationConfig = None,
        base_url: str = None
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.config = config or GenerationConfig()
        self.base_url = base_url or self.config.base_url
        
        client_kwargs = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
            
        self.client = AsyncOpenAI(**client_kwargs)
    
    async def list_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        try:
            models = await self.client.models.list()
            # 过滤并排序支持的模型
            supported_prefixes = ('gpt-4o', 'claude-3-5', 'gemini-1.5', 'deepseek-')
            unsupported_keywords = ['vision', 'instruct', 'embedding', 'audio', 'dalle', 'realtime', 'search', 'haiku']
            chat_models = []
            
            for model in models.data:
                if any(model.id.startswith(prefix) for prefix in supported_prefixes):
                    # 排除一些特殊模型（如果需要）
                    if not any(excluded in model.id.lower() for excluded in unsupported_keywords):
                        chat_models.append(model.id)
            
            return sorted(chat_models)
        except Exception as e:
            print(f"获取模型列表时出错: {str(e)}")
            # 返回基础模型作为后备选项
            return ["claude-3-5-sonnet-latest", "claude-3-5-sonnet-20241022"]

    async def generate_single_document(
        self,
        message: str,
        index: int
    ) -> str:
        """生成单个文档"""
        try:
            response = await self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "user", "content": message}
                ],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens
            )
            return response.choices[0].message.content
        except Exception as e:
            raise Exception(f"生成第 {index} 个文档时出错: {str(e)}")

    async def generate_documents(
        self,
        message: str,
        num_docs: int,
        progress_callback: Optional[Callable[[float], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> List[str]:
        """批量生成文档"""
        all_tasks = []
        results = []
        
        # 创建所有任务
        for i in range(num_docs):
            task = self.generate_single_document(message, i+1)
            all_tasks.append(task)
        
        if status_callback:
            status_callback("正在生成文档...")
        completed = 0
        
        # 分批执行任务
        for i in range(0, len(all_tasks), self.config.max_concurrent):
            batch = all_tasks[i:i + self.config.max_concurrent]
            
            for task in asyncio.as_completed(batch):
                try:
                    result = await task
                    results.append(result)
                    completed += 1
                    if progress_callback:
                        progress_callback(completed / num_docs)
                    if status_callback:
                        status_callback(f"已完成 {completed}/{num_docs} 个文档")
                except Exception as e:
                    raise e
        
        if status_callback:
            status_callback("文档生成完成！")
        return results

    def save_documents_excel(self, documents: List[str], output_file: str):
        """将文档保存为美化的Excel文件"""
        # 创建DataFrame
        df = pd.DataFrame({
            '序号': range(1, len(documents) + 1),
            '生成时间': [datetime.now().strftime('%Y-%m-%d %H:%M:%S')] * len(documents),
            '文档内容': documents
        })
        
        # 创建Excel writer对象
        writer = pd.ExcelWriter(output_file, engine='xlsxwriter')
        df.to_excel(writer, sheet_name='生成文档', index=False)
        
        # 获取workbook和worksheet对象
        workbook = writer.book
        worksheet = writer.sheets['生成文档']
        
        # 定义格式
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4F81BD',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })
        
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter',
            'text_wrap': True
        })
        
        # 设置列宽
        worksheet.set_column('A:A', 8)   # 序号
        worksheet.set_column('B:B', 20)  # 生成时间
        worksheet.set_column('C:C', 80)  # 文档内容
        
        # 设置行高
        worksheet.set_default_row(30)
        
        # 应用格式
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # 为所有单元格应用格式
        for row in range(len(documents)):
            for col in range(len(df.columns)):
                worksheet.write(row + 1, col, df.iloc[row, col], cell_format)
        
        # 保存文件
        writer.close()
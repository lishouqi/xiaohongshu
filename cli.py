import click
import asyncio
from doc_client import DocGeneratorClient, GenerationConfig

@click.command()
@click.option('--template', '-t', type=click.Path(exists=True), help='模板文档路径')
@click.option('--description', '-d', help='生成要求描述')
@click.option('--num', '-n', default=5, help='生成文档数量')
@click.option('--concurrent', '-c', default=10, help='最大并发数（1-50）')
@click.option('--output', '-o', default='generated_docs.txt', help='输出文件路径')
@click.option('--model', default='gpt-3.5-turbo', help='OpenAI模型')
@click.option('--temperature', default=0.8, help='生成温度')
@click.option('--api-key', envvar='OPENAI_API_KEY', help='OpenAI API密钥')
@click.option('--base-url', envvar='OPENAI_API_BASE', help='OpenAI API基础URL')
def generate(template, description, num, concurrent, output, model, temperature, api_key, base_url):
    """批量文档生成器命令行工具"""
    if not api_key:
        click.echo("错误：未设置 OpenAI API 密钥")
        return

    # 读取模板文件
    with open(template, 'r', encoding='utf-8') as f:
        template_content = f.read()

    if not description:
        description = click.prompt("请输入生成要求描述")

    # 配置生成器
    config = GenerationConfig(
        model=model,
        temperature=temperature,
        base_url=base_url,
        max_concurrent=min(concurrent, 50)  # 确保不超过50
    )
    
    client = DocGeneratorClient(api_key=api_key, config=config)

    # 进度显示
    with click.progressbar(length=num, label='生成进度') as bar:
        async def run():
            return await client.generate_documents(
                template=template_content,
                description=description,
                num_docs=num,
                progress_callback=lambda p: bar.update(1),
                status_callback=lambda s: click.echo(s)
            )

        # 运行生成
        results = asyncio.run(run())

    # 保存结果
    client.save_documents(results, output)
    click.echo(f"\n文档已生成并保存至: {output}")

if __name__ == '__main__':
    generate() 
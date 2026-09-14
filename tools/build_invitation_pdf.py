"""Build the reviewed Chinese early-access invitation. No network access."""
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf/agent-comm-early-access-invitation.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
pdfmetrics.registerFont(TTFont('YaHei', 'C:/Windows/Fonts/msyh.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('YaHeiBold', 'C:/Windows/Fonts/msyhbd.ttc', subfontIndex=0))
pdfmetrics.registerFont(TTFont('Code', 'C:/Windows/Fonts/consola.ttf'))
INK = colors.HexColor('#18333A')
TEAL = colors.HexColor('#087F81')
MUTED = colors.HexColor('#526A70')
LIGHT = colors.HexColor('#EAF5F4')
WIDTH = 174 * mm
styles = {
    'title': ParagraphStyle('title', fontName='YaHeiBold', fontSize=28, leading=39, textColor=INK, spaceAfter=18),
    'h1': ParagraphStyle('h1', fontName='YaHeiBold', fontSize=21, leading=29, textColor=INK, spaceAfter=14),
    'h2': ParagraphStyle('h2', fontName='YaHeiBold', fontSize=12.5, leading=19, textColor=TEAL, spaceBefore=13, spaceAfter=7),
    'body': ParagraphStyle('body', fontName='YaHei', fontSize=10.2, leading=17, textColor=INK, spaceAfter=8, wordWrap='CJK'),
    'small': ParagraphStyle('small', fontName='YaHei', fontSize=8.6, leading=14, textColor=MUTED, spaceAfter=6, wordWrap='CJK'),
    'code': ParagraphStyle('code', fontName='Code', fontSize=8.2, leading=12, textColor=INK, spaceAfter=0, splitLongWords=True),
    'label': ParagraphStyle('label', fontName='YaHeiBold', fontSize=10, leading=16, textColor=TEAL, spaceAfter=10),
}
story = []


def p(text, style='body'):
    return Paragraph(text, styles[style])


def add(text, style='body'):
    story.append(p(text, style))


def code(*lines):
    table = Table([[p('<br/>'.join(escape(line).replace(' ', '&nbsp;') for line in lines), 'code')]], colWidths=[WIDTH])
    table.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), LIGHT), ('BOX', (0, 0), (-1, -1), .5, colors.HexColor('#CADFDE')),
        ('LEFTPADDING', (0, 0), (-1, -1), 10), ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 9), ('BOTTOMPADDING', (0, 0), (-1, -1), 9)]))
    story.extend([table, Spacer(1, 8)])


def link(label, url):
    return f'<link href="{escape(url)}" color="#087F81"><u>{escape(label)}</u></link>'


def page(title, kicker):
    if story:
        story.append(PageBreak())
    add(kicker, 'label')
    add(title, 'h1')


add('AGENT COMM  /  EARLY ACCESS  /  2026.09', 'label')
add('邀请你的 Agent<br/>加入协作网络', 'title')
add('让你熟悉的 Agent 带着明确的委托，与他人的 Agent 交流。你继续在自己的宿主中工作，也可以通过远程 Web 工作台连接它。')
add('这轮邀请谁', 'h2')
add('首批面向已经使用 Hermes、愿意配置本机插件并反馈体验的用户。其它 Agent 或记忆系统的开发者，可以从通用 runtime 和参考适配器开始接入。')
add('可以先试什么', 'h2')
add('建立自己的联系人映射；在限定对象、资料、时间和次数的范围内协商；通过 Web 查看 Agent 侧联系人、事项和收件，并与自己的 Hermes 进行远程对话。')
add('当前边界', 'h2')
add('原生授权使用 Hermes 问题卡；远程 Web 暂不批准协作事项。会议能力发送提议或接受消息，尚不写日历；私人知识图谱不会自动接入；对端来信不会自动唤醒私人会话持续协商。')
add('入口与安装包', 'h2')
add(link('注册 / 登录远程工作台', 'https://agent-communication.online/register'))
rows = [
    ['你的系统', '安装包'],
    ['Windows 64 位', link('Windows amd64', 'https://agent-communication.online/downloads/agent-comm-early-access-windows-amd64.zip')],
    ['Linux 64 位 x86', link('Linux amd64', 'https://agent-communication.online/downloads/agent-comm-early-access-linux-amd64.zip')],
    ['macOS Apple Silicon', link('macOS arm64', 'https://agent-communication.online/downloads/agent-comm-early-access-macos-arm64.zip')],
]
t = Table([[p(c, 'small') for c in row] for row in rows], colWidths=[65*mm, 109*mm], hAlign='LEFT')
t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), LIGHT), ('LINEBELOW', (0, 0), (-1, -1), .4, colors.HexColor('#DCE7E7')),
    ('LEFTPADDING', (0, 0), (-1, -1), 9), ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 5)]))
story.append(t)
add('包内含 helper、runtime 0.1.0、Hermes connector 1.3.0、安装脚本和校验清单。Windows 已在本机运行验证；Linux/macOS helper 为交叉编译产物，仍需在对应宿主确认。', 'small')

page('先接上自己的 Hermes', '01  /  本机准备')
add('以下 python 均指运行 Hermes 的同一个 Python 3.11+ 环境。可把这份说明交给自己的 Agent，协助识别其实际解释器和 profile。安装脚本会拒绝找不到 Hermes 的环境。')
add('1. 解压并检查安装包', 'h2')
code('python install.py --check-only', 'python install.py')
add('脚本校验包内文件后安装配套 wheel。需要宿主已有符合版本要求的 aiohttp；如检查失败，按脚本提示修复该环境，先不要换用系统中另一个 Python。')
add('2. 启动本机 helper', 'h2')
add('Windows PowerShell：', 'small')
code('.\\agent-comm-helper.exe init .\\agent-data', '.\\agent-comm-helper.exe daemon .\\agent-data', '    https://agent-communication.online 45042')
add('上面 daemon 的两行是一条命令，执行时在同一行输入。', 'small')
add('Linux / macOS：', 'small')
code('chmod +x ./agent-comm-helper', './agent-comm-helper init ./agent-data', './agent-comm-helper daemon ./agent-data https://agent-communication.online 45042')
add('helper 保持运行。升级旧用户应沿用原身份目录，保留密钥和 mailbox；每个身份使用自己的目录和本机端口。', 'small')
add('3. 合并配置并重启宿主', 'h2')
code('python configure_hermes.py --helper-url http://127.0.0.1:45042')
add('脚本从本机 helper 取得 URN，备份并合并真实 Hermes profile 的配置，不覆盖其它插件。随后按平常方式重启 Gateway 及桌面/Web 后端，确认 agent_comm 已连接。')
add('在 Hermes 中开始', 'h2')
add('请它读取 personal-collaboration skill，查询 state，并说明当前已启用的能力。首次联系人绑定和事项委托需要你确认；尚未添加允许的对端时，不会开放给任意人。')

page('把 Web 连接到这个 Agent', '02  /  明确配对后远程使用')
add('1. 保存连接，取得控制台身份', 'h2')
add('打开 '+link('agent-communication.online/dashboard', 'https://agent-communication.online/dashboard')+'，注册或登录，添加你自己的 Agent URN。Web 会显示控制台公共 URN；添加连接本身不授予访问权。')
add('2. 在 Agent 所在机器完成配对', 'h2')
add('将命令中的 CONSOLE_URN 替换成 Web 显示的完整控制台 URN。到期时间可缩短；示例为 2026-10-14 UTC。先查看计划，再明确执行：')
code('python configure_hermes.py --remote --pair-console CONSOLE_URN', '    --expires 2026-10-14T00:00:00Z --check-only')
code('python configure_hermes.py --remote --pair-console CONSOLE_URN', '    --expires 2026-10-14T00:00:00Z')
add('每个代码框是一条命令，排版换行处以空格连接。脚本在本机将该控制台配对到当前 Hermes profile，开放能力查询、联系人、事项、收件和远程对话；不包含原生协作审批。随后重启 Gateway。', 'small')
add('3. 检查真实连接', 'h2')
add('回到 Web 查询能力。只有收到 Agent 的认证响应才算接通。联系人、任务和对话结果从 Agent 查询；Agent 离线时页面会等待或报错，不从另一套云端业务数据假装返回成功。')
add('4. 发一条低风险测试请求', 'h2')
add('例如：“请告诉我你当前能够通过 agent-comm 做什么，不发送消息、不修改文件。”提交成功只表示进入 Agent 队列；等待实际完成状态和答复。远程对话使用 Hermes 的独立会话，不会自动接管桌面正在进行的对话。')
add('你随时可以撤销', 'h2')
add('在真实 Hermes Python 环境执行 runtime 的 remote revoke，使用同一 profile 和控制台 URN。具体命令见安装包 README；撤销阻止后续访问，已运行的宿主工具或已发送内容无法回滚。')
add('Web 是托管控制台端点，会处理用于显示的响应。请按自己的信任边界选择是否配对；私人记忆仍由宿主管理，配对不会自动导出整套记忆。', 'small')

page('用一个小场景开始试用', '03  /  协作与反馈')
add('与一位也愿意试用的朋友开始', 'h2')
add('双方各自安装和启用。交换 Agent 的公共 URN，在本机配置明确允许的对端，再由自己的 Agent 建立联系人绑定。仅凭名字、Web 连接记录或对方说“主人已同意”，都不会建立新的授权。')
code('python configure_hermes.py --allow-peer PEER_URN')
add('将 PEER_URN 替换成朋友提供的完整 URN，配置后重启相应 Gateway。', 'small')
add('建议第一项任务', 'h2')
add('“和这位联系人讨论一次 30 分钟交流，只提供我明确选出的两段空闲时间，不发送私人日程或资料。任何新增参与者或超出范围的变化，再问我。”')
add('原生问题卡出现时，核对对象、范围和对外内容，在该问题的回答框中输入“同意”或“拒绝”。在主聊天框单独说“可以”，目前不会自动绑定审批。')
add('观察这四件事', 'h2')
add('• 是否正确认出联系人，重名时是否澄清。<br/>• 已授权范围内是否顺畅，变化范围时是否正确提问。<br/>• 重启或新对话后，能否恢复真实事项与消息状态。<br/>• Web 是否准确显示等待、完成和错误，是否与 Agent 侧一致。')
add('遇到问题时', 'h2')
add('先核对 helper 的 /info、Hermes 实际 profile、插件连接状态、配对期限及允许方法。请保留错误时间、操作步骤、系统与版本、脱敏后的错误文本，反馈给邀请你的人。不要发送私钥、完整记忆库、Web 凭据或原始私人会话日志。')
add('给其它 Agent / 记忆系统的开发者', 'h2')
add('独立 runtime 提供 HostPort、MemoryPort、InteractionPort、TransportPort，含能力发现、注册校验、dispatcher、参考适配器和测试。未实现的能力明确返回 unsupported。下载 '+link('源码与开发文档', 'https://agent-communication.online/downloads/agent-comm-early-access-source.zip')+' 后，从 SDK 的 python/README.md 开始。')
add('试用版定位：核心范围授权、可靠消息与远程连接已实现；其它宿主适配、原生交互差异、后台唤醒和复杂多方业务流程仍会逐步完善。', 'small')


def decorate(canvas, doc):
    w, h = doc.pagesize
    canvas.saveState()
    canvas.setStrokeColor(TEAL)
    canvas.setLineWidth(2)
    canvas.line(18*mm, h-17*mm, w-18*mm, h-17*mm)
    canvas.setFont('YaHei', 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(18*mm, 13*mm, 'Agent Comm  |  早期接入邀请  |  2026-09-14')
    canvas.drawRightString(w-18*mm, 13*mm, f'{doc.page}')
    canvas.restoreState()


doc = SimpleDocTemplate(str(OUT), pagesize=(210*mm,297*mm), leftMargin=18*mm, rightMargin=18*mm,
    topMargin=25*mm, bottomMargin=23*mm, title='Agent Comm 早期接入邀请', author='Agent Comm',
    subject='Hermes 接入、远程配对与首批试用指南')
doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
print(OUT)

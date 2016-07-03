from PyQt4.QtGui import *
from PyQt4.QtCore import *

from hashmal_lib.core.script import Script, get_asm_context, get_txscript_context
from hashmal_lib.gui_utils import monospace_font, settings_color

class ScriptEdit(QTextEdit):
    """Script editor.

    Keeps an internal Script instance that it updates
    with its text, and uses to convert formats.
    """
    def __init__(self, parent=None):
        super(ScriptEdit, self).__init__(parent)
        self.setTabStopWidth(40)
        self.needs_compilation = False
        self.current_format = 'ASM'
        self.script = Script()
        self.textChanged.connect(self.on_text_changed)
        self.setFont(monospace_font)
        # For tooltips
        self.context = []

    def on_text_changed(self):
        text = str(self.toPlainText())
        if text:
            # Get ASM context after every text change.
            if self.current_format == 'ASM':
                try:
                    self.context = get_asm_context(text)
                except Exception:
                    pass
            elif self.current_format == 'TxScript':
                try:
                    self.context = get_txscript_context(text)
                except Exception:
                    pass
        self.needs_compilation = True

    def compile_input(self):
        text = str(self.toPlainText())
        self.set_data(text, self.current_format)

    def copy_hex(self):
        txt = self.get_data('Hex')
        QApplication.clipboard().setText(txt)

    def contextMenuEvent(self, e):
        menu = self.createStandardContextMenu()
        menu.addAction('Copy Hex', self.copy_hex)
        menu.exec_(e.globalPos())

    def set_format(self, fmt):
        self.current_format = fmt
        self.setPlainText(self.get_data())

    def set_data(self, text, fmt):
        script = None
        self.context = []
        if fmt == 'Hex' and len(text) % 2 == 0:
            try:
                script = Script(text.decode('hex'))
            except Exception:
                pass
        elif fmt == 'ASM':
            try:
                self.context = get_asm_context(text)
                script = Script.from_asm(text)
            except Exception:
                pass
        elif fmt == 'TxScript':
            try:
                self.context = get_txscript_context(text)
                script = Script.from_txscript(text)
            except Exception:
                pass
        self.script = script

    def get_data(self, fmt=None):
        if self.needs_compilation:
            self.compile_input()
            self.needs_compilation = False

        if fmt is None:
            fmt = self.current_format
        if not self.script: return ''
        if fmt == 'Hex':
            return self.script.get_hex()
        elif fmt == 'ASM':
            return self.script.get_asm()
        # TODO: Inform user that TxScript is not a target language.
        elif fmt == 'TxScript':
            pass
        return ''

    def event(self, e):
        if e.type() == QEvent.ToolTip:
            cursor = self.cursorForPosition(e.pos())
            context = self.get_tooltip(cursor.position())
            if not context:
                QToolTip.hideText()
            else:
                QToolTip.showText(e.globalPos(), context)
            return True
        return super(ScriptEdit, self).event(e)

    def get_tooltip(self, index):
        """Returns the contextual tip for the word at index."""
        if index < 0 or len(self.toPlainText()) < index:
            return ''
        for start, end, value, match_type in self.context:
            if index >= start and index < end:
                return '{} ({})'.format(value, match_type)


class ScriptHighlighter(QSyntaxHighlighter):
    """Highlights variables, etc. with colors from QSettings."""
    def __init__(self, gui, script_edit):
        super(ScriptHighlighter, self).__init__(script_edit)
        self.gui = gui
        self.editor = script_edit

    def highlightBlock(self, text):
        """Use the ScriptEdit's context attribute to highlight."""
        if len(self.editor.context) == 0:
            return

        settings = self.gui.qt_settings
        offset = self.currentBlock().position()
        for start, end, value, match_type in self.editor.context:
            start = start - offset
            end = end - offset
            idx = start
            length = end - start
            fmt = QTextCharFormat()
            if match_type == 'Variable':
                length += 1 # account for '$' prefix
                var_name = str(text[idx+1: idx+length]).strip()
                if self.gui.plugin_handler.get_plugin('Variables').ui.get_key(var_name):
                    fmt.setForeground(settings_color(settings, 'variables'))
            elif match_type == 'String literal':
                fmt.setForeground(settings_color(settings, 'strings'))
            elif match_type == 'Comment':
                fmt.setForeground(settings_color(settings, 'comments'))
            elif match_type == 'Type name':
                fmt.setForeground(settings_color(settings, 'typenames'))
            elif match_type.startswith('Keyword'):
                fmt.setForeground(settings_color(settings, 'keywords'))
            elif match_type.startswith('Conditional'):
                fmt.setForeground(settings_color(settings, 'conditionals'))
            elif match_type.startswith('Boolean operator'):
                fmt.setForeground(settings_color(settings, 'booleanoperators'))
            self.setFormat(idx, length, fmt)
        return

class ScriptEditor(ScriptEdit):
    """Main script editor.

    Requires the main window as an argument so it can integrate tools.
    """
    def __init__(self, gui, parent=None):
        super(ScriptEditor, self).__init__(gui)
        self.gui = gui
        self.highlighter = ScriptHighlighter(self.gui, self)

    def contextMenuEvent(self, e):
        menu = self.createStandardContextMenu()
        menu.addAction('Copy Hex', self.copy_hex)
        menu.exec_(e.globalPos())

    def rehighlight(self):
        self.highlighter.rehighlight()

    def insertFromMimeData(self, source):
        """Rehighlight the script after pasting."""
        super(ScriptEditor, self).insertFromMimeData(source)
        self.rehighlight()

    @pyqtProperty(str)
    def asmText(self):
        return self.get_data(fmt='ASM')

    @asmText.setter
    def asmText(self, value):
        self.setText(str(value))


import { useContext, useEffect, useRef, useState } from 'react';
import { LoaderCircle, MessageCircle, Send, X } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { askDatabase } from '../services/api';

export const Chatbot = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [messages, setMessages] = useState([
    {
      from: 'bot',
      text: language === 'es'
        ? 'Hola. Soy Kenneth, el asistente del sistema. ¿En qué puedo ayudarte?'
        : 'Hello. I am Kenneth, the system assistant. How can I help you?',
    },
  ]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open, sending]);

  const buildHistory = () => messages
    .slice(-6)
    .map((message) => ({
      role: message.from === 'user' ? 'user' : 'assistant',
      content: message.text,
    }));

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || sending) return;

    const history = buildHistory();

    setMessages((prev) => [
      ...prev,
      { from: 'user', text },
    ]);
    setInput('');
    setSending(true);

    try {
      const result = await askDatabase(text, history);

      setMessages((prev) => [
        ...prev,
        {
          from: 'bot',
          text: result.answer,
          mode: result.mode,
          performance: result.performance,
        },
      ]);
    } catch (error) {
      console.error('Error consultando el asistente:', error);

      setMessages((prev) => [
        ...prev,
        {
          from: 'bot',
          text:
            language === 'es'
              ? `No pude completar la consulta. ${error.message || 'Intenta reformularla.'}`
              : `I could not complete the query. ${error.message || 'Try rephrasing it.'}`,
        },
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  return (
    <>
      {open && (
        <div
          className="fixed z-50 bottom-24 right-5 sm:right-7 w-[calc(100vw-2.5rem)] sm:w-[380px] overflow-hidden rounded-2xl border shadow-2xl"
          style={{ backgroundColor: colors.card, borderColor: colors.border }}
        >
          <div className="px-4 py-3 flex items-center justify-between" style={{ backgroundColor: theme.primary, color: '#fff' }}>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full overflow-hidden bg-white/15 flex items-center justify-center">
                <img
                  src="https://raw.githubusercontent.com/EmaCst/Fotos/main/Kenett.jpeg"
                  alt="Kenneth"
                  className="w-full h-full rounded-full object-cover"
                />
              </div>
              <div>
                <p className="font-bold">Kenneth</p>
                <p className="text-xs opacity-80">
                  {sending
                    ? (language === 'es' ? 'Analizando...' : 'Analyzing...')
                    : (language === 'es' ? 'Asistente del sistema' : 'System assistant')}
                </p>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="p-2 rounded-lg hover:bg-white/10" aria-label="Cerrar chatbot">
              <X size={19} />
            </button>
          </div>

          <div className="h-80 overflow-y-auto p-4 space-y-3" style={{ backgroundColor: colors.panel }}>
            {messages.map((message, index) => (
              <div key={`${message.from}-${index}`} className={`flex ${message.from === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className="max-w-[82%] rounded-2xl px-3.5 py-2.5 text-sm leading-5"
                  style={message.from === 'user'
                    ? { backgroundColor: theme.primary, color: '#fff' }
                    : { backgroundColor: colors.cardSoft, color: colors.text, border: `1px solid ${colors.border}` }}
                >
                  {message.text}
                </div>
              </div>
            ))}

            {sending && (
              <div className="flex justify-start">
                <div
                  className="rounded-2xl px-3.5 py-2.5 text-sm flex items-center gap-2"
                  style={{ backgroundColor: colors.cardSoft, color: colors.muted, border: `1px solid ${colors.border}` }}
                >
                  <LoaderCircle size={15} className="animate-spin" />
                  {language === 'es' ? 'Consultando datos...' : 'Querying data...'}
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <div className="p-3 border-t" style={{ borderColor: colors.border, backgroundColor: colors.card }}>
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                disabled={sending}
                placeholder={language === 'es' ? 'Escribe un mensaje...' : 'Type a message...'}
                className="min-w-0 flex-1 rounded-xl border px-3 py-2.5 outline-none focus:ring-2 disabled:opacity-60"
                style={{ backgroundColor: colors.cardSoft, borderColor: colors.border, color: colors.text, '--tw-ring-color': `${theme.primary}55` }}
              />
              <button
                onClick={sendMessage}
                disabled={sending || !input.trim()}
                className="w-11 h-11 rounded-xl flex items-center justify-center text-white shrink-0 disabled:opacity-50"
                style={{ backgroundColor: theme.primary }}
                aria-label={language === 'es' ? 'Enviar mensaje' : 'Send message'}
              >
                {sending ? <LoaderCircle size={18} className="animate-spin" /> : <Send size={18} />}
              </button>
            </div>
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((value) => !value)}
        className="fixed z-50 bottom-5 right-5 sm:right-7 w-14 h-14 rounded-full text-white flex items-center justify-center shadow-xl transition-all hover:scale-105 focus:outline-none focus:ring-4"
        style={{ backgroundColor: theme.primary, '--tw-ring-color': `${theme.primary}44` }}
        aria-label={open ? 'Cerrar chatbot' : 'Abrir chatbot'}
        title={open ? 'Cerrar chatbot' : 'Abrir chatbot'}
      >
        {open ? <X size={24} /> : <MessageCircle size={25} />}
      </button>
    </>
  );
};

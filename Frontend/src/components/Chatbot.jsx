import { useContext, useEffect, useRef, useState } from 'react';
import { Bot, MessageCircle, Send, X } from 'lucide-react';
import { DashboardContext } from '../context/DashboardContext';
import { askDatabase } from '../services/api';

export const Chatbot = () => {
  const { theme, colors, language } = useContext(DashboardContext);
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState([
    {
      from: 'bot',
      text: language === 'es'
        ? 'Hola. Soy el asistente del sistema. ¿En qué puedo ayudarte?'
        : 'Hello. I am the system assistant. How can I help you?',
    },
  ]);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const sendMessage = async () => {
  const text = input.trim();

  if (!text) return;

  // Mostrar mensaje del usuario
  setMessages((prev) => [
    ...prev,
    {
      from: 'user',
      text,
    },
  ]);

  setInput('');

  try {
    const result = await askDatabase(text);

    setMessages((prev) => [
      ...prev,
      {
        from: 'bot',
        text: result.answer,
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
            ? 'Ocurrió un error al consultar el asistente.'
            : 'An error occurred while contacting the assistant.',
      },
    ]);
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
              <div className="w-9 h-9 rounded-full bg-white/15 flex items-center justify-center">
                <Bot size={20} />
              </div>
              <div>
                <p className="font-bold">Chatbot</p>
                <p className="text-xs opacity-80">{language === 'es' ? 'Asistente del sistema' : 'System assistant'}</p>
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
            <div ref={messagesEndRef} />
          </div>

          <div className="p-3 border-t" style={{ borderColor: colors.border, backgroundColor: colors.card }}>
            <div className="flex items-center gap-2">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={language === 'es' ? 'Escribe un mensaje...' : 'Type a message...'}
                className="min-w-0 flex-1 rounded-xl border px-3 py-2.5 outline-none focus:ring-2"
                style={{ backgroundColor: colors.cardSoft, borderColor: colors.border, color: colors.text, '--tw-ring-color': `${theme.primary}55` }}
              />
              <button
                onClick={sendMessage}
                className="w-11 h-11 rounded-xl flex items-center justify-center text-white shrink-0"
                style={{ backgroundColor: theme.primary }}
                aria-label={language === 'es' ? 'Enviar mensaje' : 'Send message'}
              >
                <Send size={18} />
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

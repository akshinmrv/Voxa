#!/bin/bash
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== Voxa: Installation ===${NC}"

# 1. Install system packages
if [ -f /etc/fedora-release ]; then
    echo -e "${GREEN}[1/4] Installing Fedora system dependencies...${NC}"
    sudo dnf install -y python3.10 python3.10-devel ffmpeg
fi

# 2. Environment
echo -e "${GREEN}[2/4] Creating venv (Python 3.10)...${NC}"
python3.10 -m venv venv
source venv/bin/activate

# 3. Libraries
echo -e "${GREEN}[3/4] Installing Python libraries...${NC}"
pip install --upgrade pip
pip install -r install.txt

# 4. Creating run.sh (Execution wrapper)
echo -e "${GREEN}[4/4] Creating run.sh...${NC}"
cat <<EOF > run.sh
#!/bin/bash
source $(pwd)/venv/bin/activate
if [ "\$1" == "--help" ] || [ "\$1" == "-h" ] || [ -z "\$1" ]; then
    echo "Voxa - Help"
    echo "--------------------------------"
    echo "Usage: ./run.sh [video_file] [options]"
    echo ""
    echo "Options:"
    echo "  --tts [edge|piper|xtts|openai]   TTS Engine (default: edge)"
    echo "  --target_lang [code]             Target language (default: ru)"
    echo "  --translator [google|ollama|openai|anthropic]  Translation engine (default: google)"
    echo "  --voice-sample [file.wav]        Reference voice sample for XTTS (optional)"
    echo "  --openai_model [model]           OpenAI model name (default: gpt-5)"
    echo "  --ollama_model [model]           Ollama model name (default: llama3)"
    echo ""
    echo "Examples:"
    echo "  ./run.sh video.mp4 --tts piper"
    echo "  ./run.sh video.mp4 --tts xtts --voice-sample my_voice.wav"
    echo "  ./run.sh video.mp4 --target_lang en --translator openai"
    exit 0
fi
python $(pwd)/voxa.py "\$@"
EOF

chmod +x run.sh

echo -e "${GREEN}Done! Now use ${BLUE}./run.sh --help${GREEN} to view available commands.${NC}"

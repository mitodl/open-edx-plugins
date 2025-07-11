function OLChatBlock(runtime, element, init_args) {
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(';').shift();
    }

    import("https://cdn.jsdelivr.net/npm/@mitodl/smoot-design@0.0.0-b703deb/dist/bundles/aiChat.es.js").then(aiChat => {
        const requestOpts = {
            apiUrl: runtime.handlerUrl(element, 'ol_chat'),
            transformBody: (messages) => {
                return {
                    message: messages[messages.length - 1].content,
                }
            },
            fetchOpts: {
                headers: {
                    'X-CSRFToken': getCookie('csrftoken'),
                },
            },
        }
        aiChat.init(
            {
                requestOpts,
                entryScreenEnabled: false,
                askTimTitle: "About this Course",
                initialMessages: [
                    {
                        role: "assistant",
                        content: "How can I help you today?",
                    },
                ],
            },
            {
                container: document.getElementById("ai-chat-container"),
            },
        )
    }).catch(error => {
        console.error("Failed to load module:", error);
    });
}

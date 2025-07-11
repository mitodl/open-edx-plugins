function OLChatBlock(runtime, element, init_args) {
    import("https://cdn.jsdelivr.net/npm/@mitodl/smoot-design@0.0.0-b703deb/dist/bundles/aiChat.es.js").then(aiChat => {
        // console.log(split('; ').find(row => row.startsWith('csrftoken=')))
        const requestOpts = {
            apiUrl: runtime.handlerUrl(element, 'ol_chat'),
            transformBody: (messages) => {
                return {
                    message: messages[messages.length - 1].content,
                }
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

function OLChatBlock(runtime, element, init_args) {
    import("https://cdn.jsdelivr.net/npm/@mitodl/smoot-design@6.13.0/dist/bundles/aiChat.es.js").then(aiChat => {
        var studioRuntime = new window.StudioRuntime.v1();
        const requestOpts = {
            apiUrl: studioRuntime.handlerUrl(element, 'ol_chat'),
            transformBody: (messages) => {
                return {
                    message: messages[messages.length - 1].content,
                }
            },
            csrfHeaderName: "X-CSRFToken",
            csrfCookieName: "csrftoken",
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
                container: document.getElementById(`ai-chat-container-${init_args.block_id}`),
            },
        )
    }).catch(error => {
        console.error("Failed to load module:", error);
    });
}

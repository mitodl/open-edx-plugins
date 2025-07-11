function OLChatBlock(runtime, element, init_args) {
    import("https://unpkg.com/@mitodl/smoot-design@0.0.0-045ab6a/dist/bundles/aiChat.es.js").then(aiChat => {
        var studioRuntime = new window.StudioRuntime.v1();
        const requestOpts = {
            apiUrl: studioRuntime.handlerUrl(element, 'ol_chat'),
            transformBody: (messages) => {
                return {
                    collection_name: "content_files",
                    message: messages[messages.length - 1].content,
                    course_id: "course-v1:xPRO+PCDEx",
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

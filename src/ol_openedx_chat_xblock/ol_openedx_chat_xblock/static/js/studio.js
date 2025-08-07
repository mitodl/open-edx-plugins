function OLChatBlock(runtime, element, init_args) {
    import("https://cdn.jsdelivr.net/npm/@mitodl/smoot-design@0.0.0-d50fa6e/dist/bundles/aiChat.es.js").then(aiChat => {
        var studioRuntime = new window.StudioRuntime.v1();
        const requestOpts = {
            apiUrl: studioRuntime.handlerUrl(element, 'ol_chat'),
            transformBody: (messages, { problem_set_title }) => {
                return {
                    message: messages[messages.length - 1].content,
                    problem_set_title
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
                problemSetListUrl: "https://api.rc.learn.mit.edu/ai/api/v0/problem_set_list/?run_readable_id=14566-kaleba%3A20211202%2Bcanvas",
                problemSetInitialMessages: [
                    {
                        role: "assistant",
                        content: "Which question are you working on?",
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

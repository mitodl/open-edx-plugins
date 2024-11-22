function AiChatAsideView(runtime, element) {
    $('.chat-button').on('click', function () {
        const blockKey = $(this).data("block-key")
        const chatWindowSelector = '#chat-window-' + blockKey
        const chatButtonSelector = '#chat-button-' + blockKey
        $(chatWindowSelector).fadeIn();
        $(chatButtonSelector).hide();
    });

    // Close chat window
    $('.close-chat').on('click', function () {
        const blockKey = $(this).data("block-key")
        const chatWindowSelector = '#chat-window-' + blockKey
        const chatButtonSelector = '#chat-button-' + blockKey
        $(chatWindowSelector).fadeOut();
        $(chatButtonSelector).fadeIn();
    });

    // Send message
    function sendMessage() {
        const message = $('.chat-input').val().trim();
        if (message !== '') {
            // Display user message
            const userMessage = $('<p>')
                .addClass('user-message')
                .text(message);
            $('.chat-body').append(userMessage);

            // Clear input field
            $('.chat-input').val('');

            // Simulate bot response
            // setTimeout(() => {
            //     const botMessage = $('<p>')
            //         .addClass('bot-message')
            //         .text('Thanks for reaching out! We will get back to you shortly.');
            //     $('.chat-body').append(botMessage);
            //
            //     // Scroll to the bottom of the chat body
            //     $('.chat-body').scrollTop($('.chat-body')[0].scrollHeight);
            // }, 1000);

            // Scroll to the bottom after user message
            $('.chat-body').scrollTop($('.chat-body')[0].scrollHeight);

            $.ajax({
                type: "POST",
                url: runtime.handlerUrl(element, 'mock_handler'),
                data: JSON.stringify({"message": message}),
                success: function(resp) {
                    console.log(resp.message)
                    setTimeout(() => {
                        const botMessage = $('<p>')
                            .addClass('bot-message')
                            .text(resp.message);
                        $('.chat-body').append(botMessage);

                        $('.chat-body').scrollTop($('.chat-body')[0].scrollHeight);
                        }, 1000
                    );
                }
            });
        }
    }

    // Send message on button click
    $('.send-button').on('click', sendMessage);

    // Send message on pressing Enter
    $('.chat-input').on('keypress', function (event) {
        if (event.which === 13) {
            sendMessage();
        }
    });
}

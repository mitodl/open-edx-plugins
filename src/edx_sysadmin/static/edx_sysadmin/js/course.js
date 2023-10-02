function getCourseGitDetails(button, apiUrl, gitDirectory) {
    let tds = button.parentElement.parentElement.children;
    button.disabled = true;
    $.ajax(
        {
            url: apiUrl,
            type: "GET",
            data: {
                "courseDir": gitDirectory,
            },
            success: function(result){
                tds[2].innerHTML = result.commit ? result.commit : "Not Found";
                tds[3].innerHTML = result.date ? result.date : "Not Found";
                tds[4].innerHTML = result.author ? result.author : "Not Found";
                button.textContent = "Update Details"
                button.disabled = false;
            },
            error: function(){
                tds[2].innerHTML = "Error, Try Again";
                tds[3].innerHTML = "Error, Try Again";
                tds[4].innerHTML = "Error, Try Again";
                button.disabled = false;
            },
        }
    );
}

document.addEventListener("DOMContentLoaded", function () {
    const forgotPasswordLink = document.getElementById("forgot-password-link");
    const emailInput = document.getElementById("email");

    if (forgotPasswordLink) {
        forgotPasswordLink.addEventListener("click", function (event) {
            event.preventDefault();
            const email = emailInput.value.trim();

            if (!email) {
                alert("Please enter your email before requesting a password reset.");
                return;
            }

            fetch("/reset_password_request", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({ email: email })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert("An email has been sent to reset your password.");
                } else {
                    alert(data.error);
                }
            })
            .catch(error => console.error("Error:", error));
        });
    }
});

#!groovy

pipeline {
    agent {
        label 'polarion-testing-latest'
    }
    triggers {
        pollSCM('H/5 * * * *')
    }
    options {
        ansiColor('xterm')
        disableConcurrentBuilds()
        timestamps()
    }
    stages {
        stage('Install uv') {
            steps {
                sh "curl -LsSf https://astral.sh/uv/install.sh | sh"
                sh "export PATH=\"\$HOME/.local/bin:\$PATH\" && uv --version"
            }
        }
        stage('Install Python requirements') {
            steps {
                sh '''
                    export PATH="$HOME/.local/bin:$PATH"
                    uv sync --frozen
                '''
            }
        }
        stage('Run system tests with tox') {
            steps {
                withCredentials([
                    string(credentialsId: 'POLARION-system-test-url', variable: 'POLARION_BASE_URL'),
                    string(credentialsId: 'POLARION-system-test-token', variable: 'AUTH_TOKEN')
                ]) {
                    sh '''
                        export PATH="$HOME/.local/bin:$PATH"
                        uv run tox -- --app_url ${POLARION_BASE_URL} --app_token ${AUTH_TOKEN}
                    '''
                }
            }
        }
    }
    post {
        always {
            junit skipPublishingChecks: true, testResults: '**/TEST-*.xml'
            archiveArtifacts artifacts: '**/test-data/output/**/*.png', allowEmptyArchive: true
        }
    }
}

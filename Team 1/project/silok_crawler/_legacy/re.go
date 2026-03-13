package main

import (
	"bufio"
	"encoding/xml"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/PuerkitoBio/goquery"
)

// =====================================================================
const SaveDir = "./Sillok_Corpus_Final"
const TargetList = "need_recrawl_list.txt"

// 스마트 프록시 인증 정보
const ProxyAddress = "http://smart-to755q744pvv_area-KR:jQIb39IsTvnjkBL1@proxy.smartproxy.net:3120"
const MaxWorkers = 12 // 오리지널과 동일한 병렬 워커 수
// =====================================================================

type Article struct {
	ID          string `xml:"id,attr"`
	Translation string `xml:"translation"`
	Original    string `xml:"original"`
}

type Corpus struct {
	XMLName  xml.Name  `xml:"corpus"`
	Articles []Article `xml:"article"`
}

type PatchJob struct {
	ID string
}

type PatchResult struct {
	Article Article
	Success bool
}

var (
	reSpace   = regexp.MustCompile(`[ \t]+`)
	reNewline = regexp.MustCompile(`\n+`)
)

func cleanText(s string) string {
	s = reSpace.ReplaceAllString(s, " ")
	s = strings.ReplaceAll(s, " \n", "\n")
	s = strings.ReplaceAll(s, "\n ", "\n")
	s = reNewline.ReplaceAllString(s, "\n")
	return strings.TrimSpace(s)
}

func init() { rand.Seed(time.Now().UnixNano()) }

func fetchArticle(targetUrl string) (string, string, string) {
	proxyURL, _ := url.Parse(ProxyAddress)
	client := &http.Client{
		Transport: &http.Transport{Proxy: http.ProxyURL(proxyURL)},
		Timeout:   15 * time.Second,
	}

	req, _ := http.NewRequest("GET", targetUrl, nil)
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

	resp, err := client.Do(req)
	if err != nil { return "ERROR", "", "" }
	defer resp.Body.Close()

	if resp.StatusCode == 404 { return "NONE", "", "" }
	if resp.StatusCode != 200 { return "ERROR", "", "" }

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil { return "ERROR", "", "" }

	doc.Find("br").ReplaceWithHtml("\n")
	doc.Find("p").AppendHtml("\n")
	doc.Find("script, style, div.ins_nav, div.btn_area, div.print_area, span.url_copy").Remove()

	left := cleanText(doc.Find("div.view-item.left").Text())
	right := cleanText(doc.Find("div.view-item.right").Text())

	return "OK", left, right
}

// 오리지널 구조를 계승한 전문 워커 풀
func worker(id int, jobs <-chan PatchJob, results chan<- PatchResult, wg *sync.WaitGroup) {
	defer wg.Done()
	for job := range jobs {
		url := "https://sillok.history.go.kr/id/" + job.ID
		status, trans, orig := "ERROR", "", ""
		
		// 유료 프록시 IP 로테이션 로직 (오리지널 동일)
		for retry := 0; retry < 5; retry++ {
			status, trans, orig = fetchArticle(url)
			if status != "ERROR" { break }
			fmt.Printf("🚨 [워커 %02d] 지연 감지. 자동 IP 로테이션 중... (%d/5) - ID: %s\n", id, retry+1, job.ID)
			time.Sleep(1 * time.Second)
		}

		if status == "OK" {
			fmt.Printf("   ✅ [워커 %02d] %s 복구 완료\n", id, job.ID)
			results <- PatchResult{
				Article: Article{ID: job.ID, Translation: trans, Original: orig},
				Success: true,
			}
		} else {
			fmt.Printf("   ❌ [워커 %02d] %s 복구 최종 실패\n", id, job.ID)
			results <- PatchResult{Success: false}
		}
		
		// 서버 부하 방지 딜레이
		time.Sleep(time.Duration(rand.Intn(500)+500) * time.Millisecond)
	}
}

func main() {
	fmt.Println("==================================================")
	fmt.Println("🚀 손상 데이터 핀포인트 복구(Patcher) 엔진 가동 🚀")
	fmt.Println("==================================================")

	file, err := os.Open(TargetList)
	if err != nil {
		fmt.Printf("⚠️ 리스트 파일을 찾을 수 없습니다: %s\n", err)
		return
	}
	defer file.Close()

	var targetIDs []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		id := strings.TrimSpace(scanner.Text())
		if id != "" { targetIDs = append(targetIDs, id) }
	}

	if len(targetIDs) == 0 {
		fmt.Println("✅ 복구할 ID가 없습니다. 완벽합니다!")
		return
	}

	// 파일명 단위로 타겟 그룹화
	fileGroups := make(map[string][]string)
	for _, id := range targetIDs {
		if len(id) < 8 { continue }
		kingCode := id[1:2] 
		yearStr := id[5:7]  
		year, _ := strconv.Atoi(yearStr)
		filename := fmt.Sprintf("%s/sillok_%s_%02d.xml", SaveDir, kingCode, year)
		fileGroups[filename] = append(fileGroups[filename], id)
	}

	// 파일별로 복구 세션 진행
	for filename, ids := range fileGroups {
		fmt.Printf("\n📂 타겟 파일 오픈: %s (복구 대상 %d건)\n", filename, len(ids))
		
		var currentArticles []Article
		xmlFile, err := os.Open(filename)
		if err == nil {
			byteValue, _ := io.ReadAll(xmlFile)
			var corpus Corpus
			xml.Unmarshal(byteValue, &corpus)
			currentArticles = corpus.Articles
			xmlFile.Close()
		}

		// 손상된 데이터 도려내기
		var cleanArticles []Article
		badIDMap := make(map[string]bool)
		for _, badID := range ids { badIDMap[badID] = true }
		
		for _, art := range currentArticles {
			if !badIDMap[art.ID] { cleanArticles = append(cleanArticles, art) }
		}

		// 워커 풀(Worker Pool) 세팅
		jobs := make(chan PatchJob, len(ids))
		results := make(chan PatchResult, len(ids))
		var wg sync.WaitGroup

		// 워커 기동
		for w := 1; w <= MaxWorkers; w++ {
			wg.Add(1)
			go worker(w, jobs, results, &wg)
		}

		// 작업 투입
		for _, targetID := range ids {
			jobs <- PatchJob{ID: targetID}
		}
		close(jobs)

		// 모든 워커가 끝날 때까지 대기 후 결과 채널 닫기
		go func() {
			wg.Wait()
			close(results)
		}()

		// 복구된 데이터 취합 (채널에서 수신)
		successCount := 0
		for res := range results {
			if res.Success {
				cleanArticles = append(cleanArticles, res.Article)
				successCount++
			}
		}

		// 날짜(ID) 순 정렬
		sort.Slice(cleanArticles, func(i, j int) bool {
			return cleanArticles[i].ID < cleanArticles[j].ID
		})

		// [안전 저장 로직] 임시 파일(.tmp)에 먼저 쓰고 성공하면 원래 이름으로 덮어쓰기
		tmpFilename := filename + ".tmp"
		outFile, _ := os.Create(tmpFilename)
		outFile.WriteString(xml.Header)
		enc := xml.NewEncoder(outFile)
		enc.Indent("", "    ")
		enc.Encode(Corpus{Articles: cleanArticles})
		outFile.Close()
		
		os.Rename(tmpFilename, filename) // 안전하게 원본 파일 덮어쓰기
		
		fmt.Printf("💾 [%s] 복구 완료 (성공: %d / 총 타겟: %d)\n", filename, successCount, len(ids))
	}
	
	fmt.Println("\n🎉 모든 손상 데이터의 핀포인트 복구가 끝났습니다!")
}
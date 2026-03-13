package main

import (
	"encoding/xml"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"os"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/PuerkitoBio/goquery"
)

// =====================================================================
const TargetKingCode = "o"  // 영조
const StartYear = 14
const MaxYear = 15
const SaveDir = "./Sillok_Corpus_Final"

// 스마트 프록시 인증 정보 적용 완료
const ProxyAddress = "http://smart-to755q744pvv_area-KR:jQIb39IsTvnjkBL1@proxy.smartproxy.net:3120"
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

type Job struct {
	KingCode string; Year int; Month int
}

var (
	reSpace   = regexp.MustCompile(`[ \t]+`)
	reNewline = regexp.MustCompile(`\n+`)
	
	currentYearArticles []Article
	storageMu           sync.Mutex
)

func cleanText(s string) string {
	s = reSpace.ReplaceAllString(s, " ")
	s = strings.ReplaceAll(s, " \n", "\n")
	s = strings.ReplaceAll(s, "\n ", "\n")
	s = reNewline.ReplaceAllString(s, "\n")
	return strings.TrimSpace(s)
}

func init() { rand.Seed(time.Now().UnixNano()) }

// 기존 데이터 로드 (이어받기 핵심)
func loadExistingArticles(year int) {
	storageMu.Lock()
	defer storageMu.Unlock()
	filename := fmt.Sprintf("%s/sillok_%s_%02d.xml", SaveDir, TargetKingCode, year)
	file, err := os.Open(filename)
	if err != nil {
		currentYearArticles = []Article{}
		return
	}
	defer file.Close()
	var corpus Corpus
	byteValue, _ := io.ReadAll(file)
	xml.Unmarshal(byteValue, &corpus)
	currentYearArticles = corpus.Articles
	if len(currentYearArticles) > 0 {
		fmt.Printf("📂 [%d년] 기존 %d건 로드 완료. 정렬 후 수집 재개!\n", year, len(currentYearArticles))
	}
}

// 실시간 저장 + 날짜순 자동 정렬
func saveSingleArticle(year int, art Article) {
	storageMu.Lock()
	defer storageMu.Unlock()

	currentYearArticles = append(currentYearArticles, art)

	// 기사 ID순(날짜순)으로 상시 정렬
	sort.Slice(currentYearArticles, func(i, j int) bool {
		return currentYearArticles[i].ID < currentYearArticles[j].ID
	})

	filename := fmt.Sprintf("%s/sillok_%s_%02d.xml", SaveDir, TargetKingCode, year)
	f, _ := os.Create(filename)
	defer f.Close()

	f.WriteString(xml.Header)
	enc := xml.NewEncoder(f)
	enc.Indent("", "    ")
	enc.Encode(Corpus{Articles: currentYearArticles})
}

// 스마트 프록시 로테이션 엔진
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

func worker(id int, jobs <-chan Job, wg *sync.WaitGroup) {
	defer wg.Done()
	for job := range jobs {
		for isLeap := 0; isLeap <= 1; isLeap++ {
			leapMonthExists := true
			for day := 1; day <= 31; day++ {
				if !leapMonthExists { break }
				articleNum := 1
				for {
					if articleNum > 30 { break }
					targetID := fmt.Sprintf("k%sa_1%02d%02d%d%02d_%03d", job.KingCode, job.Year, job.Month, isLeap, day, articleNum)
					
					// 이어받기 체크
					storageMu.Lock()
					isDone := false
					for _, a := range currentYearArticles {
						if a.ID == targetID { isDone = true; break }
					}
					storageMu.Unlock()
					if isDone { articleNum++; continue }

					url := "https://sillok.history.go.kr/id/" + targetID
					status, trans, detail := "ERROR", "", ""
					
					// 유료 프록시는 재시도 시 IP가 자동 교체됨
					for retry := 0; retry < 5; retry++ {
						status, trans, detail = fetchArticle(url)
						if status != "ERROR" { break }
						fmt.Printf("🚨 [워커 %d] 지연 감지. 자동 IP 로테이션 중... (%d/5)\n", id, retry+1)
						time.Sleep(1 * time.Second)
					}

					if status == "NONE" {
						if isLeap == 1 && day == 1 && articleNum == 1 { leapMonthExists = false }
						break
					}

					if status == "OK" {
						saveSingleArticle(job.Year, Article{ID: targetID, Translation: trans, Original: detail})
						fmt.Printf("    ✅ [워커 %d] %s 성공\n", id, targetID)
					}
					articleNum++
					
					time.Sleep(time.Duration(rand.Intn(500)+500) * time.Millisecond)
				}
			}
		}
	}
}

func main() {
	fmt.Printf("크롤링 시작")
	os.MkdirAll(SaveDir, 0755)

	year := StartYear
	for year <= MaxYear {
		loadExistingArticles(year)
		fmt.Printf("\n---  재위 %d년 수집 시작 ---\n", year)
		
		jobs := make(chan Job, 12)
		var wg sync.WaitGroup

		for w := 1; w <= 12; w++ {
			wg.Add(1)
			go worker(w, jobs, &wg)
		}

		for m := 1; m <= 12; m++ {
			jobs <- Job{KingCode: TargetKingCode, Year: year, Month: m}
		}
		close(jobs)
		wg.Wait()
		fmt.Printf("\n💾 %d년 수집 종료.\n", year)
		year++
	}
	fmt.Println("🎉 모든 수집 완료.")
}